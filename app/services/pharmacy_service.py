from datetime import datetime

from sqlalchemy.orm import Session

from app.common.enums import PharmacyOrderStatus
from app.common.messages import Messages
from app.common.service_result import ServiceResult

from app.core.logger import logger
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    BadRequestException,
    ConflictException,
)

from app.models.medicine import Medicine
from app.models.medication_administration import MedicationAdministration


from app.models.walk_in_sale import WalkInSale
from app.schemas.pharmacy import (
    MedicineCreate,
    MedicineUpdate,
    MedicineRestock,
    WalkInDispenseRequest,
    WalkInSaleResponse,
    MedicationAdministrationCreate,
)


class PharmacyService:

    def __init__(
        self,
        medicine_repository,
        pharmacy_order_repository,
        medication_administration_repository,
        patient_repository,
        admission_repository=None,
        user_repository=None,
    ):
        self.medicine_repo = medicine_repository
        self.order_repo = pharmacy_order_repository
        self.mar_repo = medication_administration_repository
        self.patient_repo = patient_repository
        self.admission_repo = admission_repository
        self.user_repo = user_repository

    # ═════════════════════════════════════════════════════
    # Prescription → Pharmacy Order (called from EMRService
    # right after a prescription is created)
    # ═════════════════════════════════════════════════════
    
    @staticmethod
    @staticmethod
    @staticmethod
    def _estimate_quantity(frequency: str | None, duration: str | None, explicit: int | None = None) -> int:
        """qty = times_per_day × days. UI: 1 / 1+1 / 1+1+1. Ignores default quantity=1."""
        import re as _re
        times = 1
        raw = (frequency or "").strip()
        if raw:
            if "+" in raw:
                times = max(1, len([p for p in raw.split("+") if p.strip() != ""]))
            elif raw.isdigit():
                times = max(1, int(raw))
            else:
                freq = raw.upper()
                if any(x in freq for x in ("QID", "QDS", "FOUR")): times = 4
                elif any(x in freq for x in ("TID", "TDS", "THRICE", "THREE")): times = 3
                elif any(x in freq for x in ("BD", "BID", "TWICE", "TWO")): times = 2
                elif any(x in freq for x in ("OD", "QD", "ONCE", "DAILY", "STAT", "HS")): times = 1
        days = 1
        if duration:
            m = _re.search(r"(\d+)", str(duration))
            if m:
                days = max(1, int(m.group(1)))
            elif "WEEK" in str(duration).upper():
                days = 7
        return max(1, int(times) * int(days))

    def create_orders_for_prescription(self, db: Session, prescription):
        """
        One PharmacyOrder per prescription item, in pending status.
        Auto-links to the inventory Medicine record when the name
        matches, so the pharmacist sees stock availability up front.
        Runs inside the caller's existing UnitOfWork — no commit here.
        """
        from app.models.pharmacy_order import PharmacyOrder

        orders = []
        for item in prescription.items:
            form = (getattr(item, "form", None) or "").strip().lower() or None
            dosage = getattr(item, "dosage", None)
            if hasattr(self.medicine_repo, "get_by_name_form_dosage"):
                medicine = self.medicine_repo.get_by_name_form_dosage(
                    db, item.medicine_name, form=form, dosage=dosage
                )
            else:
                medicine = self.medicine_repo.get_by_name(db, item.medicine_name)
                # reject match if form conflicts
                if medicine and form and str(medicine.form).lower() != form:
                    medicine = None
            qty = self._estimate_quantity(
                getattr(item, "frequency", None),
                getattr(item, "duration", None),
                getattr(item, "quantity", None),
            )
            if hasattr(item, "quantity"):
                item.quantity = qty
            order_form = form or (medicine.form if medicine else None)
            kw = dict(
                prescription_item_id=item.id,
                patient_id=prescription.patient_id,
                medicine_id=medicine.id if medicine else None,
                status=PharmacyOrderStatus.PENDING.value,
                quantity=qty,
            )
            # set form on order when column exists
            try:
                from app.models.pharmacy_order import PharmacyOrder as _PO
                if hasattr(_PO, "form"):
                    kw["form"] = order_form
                if hasattr(_PO, "source"):
                    kw["source"] = "prescription"
            except Exception:
                pass
            orders.append(PharmacyOrder(**kw))

        if orders:
            self.order_repo.create_many(db, orders)

        self._notify_role(
            db,
            role="pharmacist",
            title="New Pharmacy Order",
            body=f"{len(orders)} medicine(s) prescribed and awaiting dispense.",
        )

        return orders

    # ═════════════════════════════════════════════════════
    # Pharmacy Order Queue
    # ═════════════════════════════════════════════════════
    def get_pending_orders(self, db: Session) -> ServiceResult:
        orders = self.order_repo.get_pending(db)
        return ServiceResult.Success(Messages.SUCCESS, self._enrich(orders))

    def get_orders_for_patient(self, db: Session, patient_id: int) -> ServiceResult:
        orders = self.order_repo.get_by_patient(db, patient_id)
        return ServiceResult.Success(Messages.SUCCESS, self._enrich(orders))

    def get_order_by_id(self, db: Session, order_id: int) -> ServiceResult:
        order = self.order_repo.get_by_id(db, order_id)
        if not order:
            raise NotFoundException(Messages.PHARMACY_ORDER_NOT_FOUND)
        return ServiceResult.Success(Messages.SUCCESS, self._enrich([order])[0])

    def _enrich(self, orders):
        """Attaches display fields for pharmacist queue: name, form, qty,
        OPD vs IPD vs ward-course, and bed location."""
        for order in orders:
            item = order.prescription_item
            # preserve DB source (prescription|course) on a separate attr
            order_source = getattr(order, "source", None) or "prescription"
            order.order_source = order_source
            order.quantity = getattr(order, "quantity", None) or 1
            order.form = getattr(order, "form", None)
            if item:
                order.medicine_name = item.medicine_name
                order.dosage = item.dosage
                order.frequency = item.frequency
                order.duration = item.duration
                # Prefer prescription form so pharmacist always sees doctor's choice
                if getattr(item, "form", None):
                    order.form = str(item.form).strip().lower()
                if not order.form and item.instructions:
                    # parse "Form: tablet" from instructions if needed
                    import re
                    m = re.search(r"Form:\s*(\w+)", item.instructions or "", re.I)
                    if m:
                        order.form = m.group(1).lower()
                prescription = item.prescription
                if prescription:
                    order.prescribing_doctor_id = prescription.doctor_id
                    if prescription.admission_id:
                        order.care_setting = "ipd"
                        order.admission_id = prescription.admission_id
                        order.ward_bed_label = self._ward_bed_label(
                            prescription.admission
                        )
                    else:
                        order.care_setting = "opd"
                else:
                    order.care_setting = "opd"
            else:
                order.care_setting = "opd"
            # inventory form badge
            if not order.form and order.medicine is not None:
                order.form = getattr(order.medicine, "form", None)
            if order.patient:
                order.patient_name = order.patient.name
            # human label for queue
            if order_source == "course":
                order.source_label = "Ward course"
            elif getattr(order, "care_setting", None) == "ipd":
                order.source_label = "IPD prescription"
            else:
                order.source_label = "OPD prescription"
        return orders

    def _ward_bed_label(self, admission):
        if not admission or not admission.bed:
            return None
        bed = admission.bed
        ward_name = bed.ward.name if bed.ward else "Ward"
        return f"{ward_name} — Bed {bed.bed_number}"

    # ═════════════════════════════════════════════════════
    # Dispense (with stock check)
    # ═════════════════════════════════════════════════════
    def dispense_order(
        self,
        db: Session,
        order_id: int,
        dispensed_by_username: str | None,
    ) -> ServiceResult:

        order = self.order_repo.get_by_id(db, order_id)
        if not order:
            raise NotFoundException(Messages.PHARMACY_ORDER_NOT_FOUND)

        if order.status == PharmacyOrderStatus.DISPENSED.value:
            raise ConflictException(Messages.PHARMACY_ORDER_ALREADY_DISPENSED)

        dispensed_by_user_id = self._resolve_user_id(db, dispensed_by_username)

        medicine = (
            self.medicine_repo.get_by_id(db, order.medicine_id)
            if order.medicine_id
            else None
        )

        if not medicine:
            # Not in the master inventory list at all — pharmacist has to
            # add it first, we can't confirm stock.
            with UnitOfWork(db):
                order.status = PharmacyOrderStatus.OUT_OF_STOCK.value
                updated = self.order_repo.update(db, order)
            raise BadRequestException(Messages.PHARMACY_ORDER_OUT_OF_STOCK)

        if medicine.stock_qty <= 0:
            with UnitOfWork(db):
                order.status = PharmacyOrderStatus.OUT_OF_STOCK.value
                self.order_repo.update(db, order)
            raise BadRequestException(Messages.PHARMACY_ORDER_OUT_OF_STOCK)

        with UnitOfWork(db):
            qty = max(1, int(getattr(order, "quantity", None) or 1))
            if medicine.stock_qty < qty:
                raise BadRequestException(
                    f"Insufficient stock for {medicine.name}: need {qty}, have {medicine.stock_qty}."
                )
            medicine.stock_qty -= qty
            self.medicine_repo.update(db, medicine)

            order.status = PharmacyOrderStatus.DISPENSED.value
            order.dispensed_by = dispensed_by_user_id
            order.dispensed_at = datetime.utcnow()
            updated = self.order_repo.update(db, order)

        logger.info(
            f"Pharmacy order dispensed | Order={order_id} | "
            f"Medicine={medicine.name} | Remaining stock={medicine.stock_qty}"
        )

        if medicine.stock_qty <= medicine.reorder_threshold:
            self._notify_role(
                db,
                role="pharmacist",
                title="Low Stock Alert",
                body=f"{medicine.name} is at {medicine.stock_qty} {medicine.unit} — reorder needed.",
            )

        return ServiceResult.Success(Messages.PHARMACY_ORDER_DISPENSED, updated)

    # ═════════════════════════════════════════════════════
    # Inventory Management
    # ═════════════════════════════════════════════════════
    def add_medicine(self, db: Session, data: MedicineCreate) -> ServiceResult:
        """Create inventory, or if name already exists restock + refresh form.
        Required for ward-course flow: pharmacist must fill stock without
        hitting "already exists" when the drug is on the shelf at qty 0.
        """
        existing = self.medicine_repo.get_by_name(db, data.name)

        with UnitOfWork(db):
            if existing:
                add_qty = max(0, int(data.stock_qty or 0))
                if add_qty > 0:
                    existing.stock_qty = int(existing.stock_qty or 0) + add_qty
                form_val = data.form.value if hasattr(data.form, "value") else data.form
                if form_val:
                    existing.form = str(form_val).lower()
                if data.unit:
                    existing.unit = data.unit
                if data.reorder_threshold is not None:
                    existing.reorder_threshold = data.reorder_threshold
                if data.batch_number:
                    existing.batch_number = data.batch_number
                if data.expiry_date:
                    existing.expiry_date = data.expiry_date
                if getattr(data, "unit_price", None) is not None:
                    existing.unit_price = float(data.unit_price)
                created = self.medicine_repo.update(db, existing)
                msg = Messages.MEDICINE_RESTOCKED
            else:
                medicine = Medicine(
                    name=data.name.strip(),
                    form=data.form.value if hasattr(data.form, "value") else data.form,
                    dosage=(str(data.dosage).strip() if getattr(data, "dosage", None) else None),
                    unit=data.unit,
                    stock_qty=data.stock_qty,
                    reorder_threshold=data.reorder_threshold,
                    unit_price=float(getattr(data, "unit_price", None) if getattr(data, "unit_price", None) is not None else 50.0),
                    batch_number=data.batch_number,
                    expiry_date=data.expiry_date,
                )
                created = self.medicine_repo.create(db, medicine)
                msg = Messages.MEDICINE_CREATED

            orphaned_orders = self.order_repo.get_unlinked_by_medicine_name(
                db, data.name
            )
            for order in orphaned_orders:
                order.medicine_id = created.id
                order.status = PharmacyOrderStatus.PENDING.value
                self.order_repo.update(db, order)

            stuck_orders = self.order_repo.get_out_of_stock_by_medicine(
                db, created.id
            )
            for order in stuck_orders:
                order.status = PharmacyOrderStatus.PENDING.value
                self.order_repo.update(db, order)

        linked = len(orphaned_orders) + len(stuck_orders)
        if linked:
            logger.info(
                f"Medicine {created.name} (id={created.id}): linked/reopened "
                f"{linked} course/Rx order(s) after add/restock"
            )

        return ServiceResult.Success(msg, created)


    def get_medicines(self, db: Session) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS, self.medicine_repo.get_all(db)
        )

    def get_low_stock_medicines(self, db: Session) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS, self.medicine_repo.get_low_stock(db)
        )

    def update_medicine(
        self, db: Session, medicine_id: int, data: MedicineUpdate
    ) -> ServiceResult:
        medicine = self.medicine_repo.get_by_id(db, medicine_id)
        if not medicine:
            raise NotFoundException(Messages.MEDICINE_NOT_FOUND)

        if data.name is not None:
            medicine.name = data.name
        if data.form is not None:
            medicine.form = data.form.value
        if getattr(data, "dosage", None) is not None:
            medicine.dosage = (str(data.dosage).strip() or None)
        if data.unit is not None:
            medicine.unit = data.unit
        if data.reorder_threshold is not None:
            medicine.reorder_threshold = data.reorder_threshold
        if getattr(data, "unit_price", None) is not None:
            medicine.unit_price = float(data.unit_price)
        if data.batch_number is not None:
            medicine.batch_number = data.batch_number
        if data.expiry_date is not None:
            medicine.expiry_date = data.expiry_date

        with UnitOfWork(db):
            updated = self.medicine_repo.update(db, medicine)

        return ServiceResult.Success(Messages.MEDICINE_UPDATED, updated)

    def restock_medicine(
        self, db: Session, medicine_id: int, data: MedicineRestock
    ) -> ServiceResult:
        medicine = self.medicine_repo.get_by_id(db, medicine_id)
        if not medicine:
            raise NotFoundException(Messages.MEDICINE_NOT_FOUND)

        if data.quantity <= 0:
            raise BadRequestException("Restock quantity must be positive.")

        with UnitOfWork(db):
            medicine.stock_qty += data.quantity
            updated = self.medicine_repo.update(db, medicine)

            # Orders that were bounced to "out_of_stock" when we had none
            # left are stuck there forever otherwise — get_pending() only
            # ever looks at status == "pending", so a restock with no
            # further action left them invisible to the queue. Put them
            # back in the queue now that stock exists again.
            stuck_orders = self.order_repo.get_out_of_stock_by_medicine(
                db, medicine_id
            )
            for order in stuck_orders:
                order.status = PharmacyOrderStatus.PENDING.value
                self.order_repo.update(db, order)

            orphaned = self.order_repo.get_unlinked_by_medicine_name(
                db, medicine.name
            )
            for order in orphaned:
                order.medicine_id = medicine_id
                order.status = PharmacyOrderStatus.PENDING.value
                self.order_repo.update(db, order)

        reopened = len(stuck_orders) + len(orphaned)
        if reopened:
            logger.info(
                f"Restock reopened {reopened} order(s) "
                f"for medicine={medicine.name} (id={medicine_id})"
            )

        return ServiceResult.Success(Messages.MEDICINE_RESTOCKED, updated)

    # ═════════════════════════════════════════════════════
    # Medication Administration Record (IPD ongoing dosing)
    # ═════════════════════════════════════════════════════
    def log_administration(
        self,
        db: Session,
        admission_id: int,
        given_by_username: str | None,
        data: MedicationAdministrationCreate,
    ) -> ServiceResult:

        if self.admission_repo:
            admission = self.admission_repo.get_by_id(db, admission_id)
            if not admission:
                raise NotFoundException(Messages.ADMISSION_NOT_FOUND)

        medicine = self.medicine_repo.get_by_id(db, data.medicine_id)
        if not medicine:
            raise NotFoundException(Messages.MEDICINE_NOT_FOUND)

        if medicine.stock_qty <= 0:
            raise BadRequestException(Messages.PHARMACY_ORDER_OUT_OF_STOCK)

        given_by_user_id = self._resolve_user_id(db, given_by_username)

        record = MedicationAdministration(
            admission_id=admission_id,
            medicine_id=data.medicine_id,
            scheduled_time=data.scheduled_time,
            given_by=given_by_user_id,
        )

        with UnitOfWork(db):
            medicine.stock_qty -= 1
            self.medicine_repo.update(db, medicine)
            created = self.mar_repo.create(db, record)

        return ServiceResult.Success(Messages.MEDICATION_ADMINISTERED, created)

    def get_administrations_for_admission(
        self, db: Session, admission_id: int
    ) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS,
            self.mar_repo.get_by_admission(db, admission_id),
        )

    # ═════════════════════════════════════════════════════
    # Notifications
    # ═════════════════════════════════════════════════════

    def walk_in_dispense(
        self,
        db: Session,
        data: "WalkInDispenseRequest",
        sold_by_username: str | None,
    ) -> ServiceResult:
        """Counter / OTC sale — no prescription or doctor order required."""
        from app.models.walk_in_sale import WalkInSale
        from app.schemas.pharmacy import WalkInSaleResponse

        qty = int(data.quantity or 0)
        if qty <= 0:
            raise BadRequestException("Quantity must be at least 1.")

        medicine = self.medicine_repo.get_by_id(db, data.medicine_id)
        if not medicine:
            raise NotFoundException(Messages.MEDICINE_NOT_FOUND)

        if medicine.stock_qty < qty:
            raise BadRequestException(
                f"Insufficient stock for {medicine.name}. "
                f"Available: {medicine.stock_qty}, requested: {qty}."
            )

        unit_price = float(getattr(medicine, "unit_price", None) or 0.0)
        total = round(unit_price * qty, 2)
        sold_by = self._resolve_user_id(db, sold_by_username)

        patient_id = data.patient_id
        customer_name = (data.customer_name or "").strip() or None
        customer_phone = (data.customer_phone or "").strip() or None
        if patient_id:
            patient = None
            if getattr(self, "patient_repo", None):
                patient = self.patient_repo.get_by_id(db, patient_id)
            if not patient:
                raise NotFoundException(Messages.PATIENT_NOT_FOUND)
            if not customer_name:
                customer_name = getattr(patient, "name", None) or f"Patient #{patient_id}"
            if not customer_phone:
                customer_phone = getattr(patient, "phone", None) or getattr(patient, "phone_number", None)

        with UnitOfWork(db):
            medicine.stock_qty -= qty
            self.medicine_repo.update(db, medicine)

            sale = WalkInSale(
                medicine_id=medicine.id,
                quantity=qty,
                patient_id=patient_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                notes=(data.notes or "").strip() or None,
                unit_price=unit_price,
                total_price=total,
                sold_by=sold_by,
            )
            db.add(sale)
            db.flush()
            db.refresh(sale)

        payload = WalkInSaleResponse(
            id=sale.id,
            medicine_id=medicine.id,
            medicine_name=medicine.name,
            form=getattr(medicine, "form", None),
            quantity=qty,
            customer_name=sale.customer_name,
            customer_phone=sale.customer_phone,
            patient_id=sale.patient_id,
            notes=sale.notes,
            unit_price=unit_price,
            total_price=total,
            sold_by=sold_by,
            created_at=sale.created_at,
        )
        return ServiceResult.Success("Walk-in sale recorded", payload)

    def list_walk_in_sales(self, db: Session, limit: int = 50) -> ServiceResult:
        from app.models.walk_in_sale import WalkInSale
        from app.schemas.pharmacy import WalkInSaleResponse
        from sqlalchemy import select

        limit = max(1, min(int(limit or 50), 200))
        rows = (
            db.execute(
                select(WalkInSale).order_by(WalkInSale.id.desc()).limit(limit)
            )
            .scalars()
            .all()
        )
        out = []
        for sale in rows:
            med = (
                self.medicine_repo.get_by_id(db, sale.medicine_id)
                if sale.medicine_id
                else None
            )
            out.append(
                WalkInSaleResponse(
                    id=sale.id,
                    medicine_id=sale.medicine_id,
                    medicine_name=med.name if med else None,
                    form=getattr(med, "form", None) if med else None,
                    quantity=sale.quantity,
                    customer_name=sale.customer_name,
                    customer_phone=sale.customer_phone,
                    patient_id=sale.patient_id,
                    notes=sale.notes,
                    unit_price=float(sale.unit_price or 0),
                    total_price=float(sale.total_price or 0),
                    sold_by=sale.sold_by,
                    created_at=sale.created_at,
                )
            )
        return ServiceResult.Success("OK", out)


    def _resolve_user_id(self, db: Session, username: str | None):
        """The JWT only carries the username — look up the numeric
        User.id for stamping dispensed_by/given_by columns."""
        if not username or not self.user_repo:
            return None
        user = self.user_repo.get_by_username(db, username)
        return user.id if user else None

    def _notify_role(self, db: Session, role: str, title: str, body: str):
        if not self.user_repo:
            return

        try:
            from app.services.firebase_service import send_notification

            users = self.user_repo.get_by_role(db, role)
            for user in users:
                if user.fcm_token:
                    send_notification(
                        token=user.fcm_token,
                        title=title,
                        body=body,
                    )
        except Exception as e:
            logger.error(f"Pharmacy notification failed: {e}")