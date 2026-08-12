from __future__ import annotations

from datetime import datetime, timezone, date
from math import ceil

from sqlalchemy.orm import Session, joinedload

from app.core.unit_of_work import UnitOfWork
from app.common.service_result import ServiceResult
from app.exceptions.exceptions import NotFoundException, BadRequestException, ConflictException
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.admission import Admission
from app.models.bed import Bed
from app.models.pharmacy_order import PharmacyOrder
from app.models.lab_order import LabOrder
from app.models.lab_result import LabResult
from app.models.lab_test import LabTest
from app.models.medicine import Medicine
from app.models.medication_course import MedicationCourseDose
from app.models.billing import Bill, BillItem
from app.models.prescription import Prescription
from app.schemas.billing import BillCreateRequest, BillPayRequest
from app.common.enums import (
    PharmacyOrderStatus,
    AdmissionStatus,
    BillStatus,
    BillItemCategory,
)

DEFAULT_CONSULTATION_FEE = 500.0
DEFAULT_MEDICINE_PRICE = 50.0
DEFAULT_LAB_PRICE = 300.0
DEFAULT_BED_RATES = {
    "general": 2000.0,
    "icu": 8000.0,
    "private": 5000.0,
    "pediatric": 2500.0,
}
DEFAULT_NURSING_PER_DOSE = 150.0
DEFAULT_NURSING_PER_DAY = 500.0


class BillingService:
    """Episode-aware billing with unbilled-only protection against double charges."""

    def search_patients(self, db: Session, query: str, limit: int = 20):
        q = (query or "").strip()
        if not q:
            return ServiceResult.Success("OK", [])
        rows = (
            db.query(Patient)
            .filter(
                (Patient.phone.ilike(f"%{q}%"))
                | (Patient.name.ilike(f"%{q}%"))
                | (Patient.email.ilike(f"%{q}%"))
            )
            .order_by(Patient.id.desc())
            .limit(limit)
            .all()
        )
        if q.isdigit():
            by_id = db.query(Patient).filter(Patient.id == int(q)).first()
            if by_id and all(r.id != by_id.id for r in rows):
                rows.insert(0, by_id)
        data = [
            {"id": p.id, "name": p.name, "phone": p.phone, "email": p.email, "care_type": p.care_type}
            for p in rows
        ]
        return ServiceResult.Success("Patients found.", data)

    def list_patient_episodes(self, db: Session, patient_id: int):
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise NotFoundException("Patient not found.")
        appts = (
            db.query(Appointment)
            .options(joinedload(Appointment.doctor))
            .filter(Appointment.patient_id == patient_id)
            .order_by(Appointment.appointment_date.desc())
            .limit(50)
            .all()
        )
        admissions = (
            db.query(Admission)
            .filter(Admission.patient_id == patient_id)
            .order_by(Admission.id.desc())
            .limit(30)
            .all()
        )

        def _st(a):
            return str(getattr(a.status, "value", a.status) or "").lower()

        return ServiceResult.Success(
            "OK",
            {
                "appointments": [
                    {
                        "id": a.id,
                        "date": a.appointment_date.isoformat() if a.appointment_date else None,
                        "time": a.appointment_time.strftime("%H:%M") if a.appointment_time else None,
                        "status": _st(a),
                        "doctor_name": a.doctor.full_name if a.doctor else None,
                        "type": str(getattr(a.appointment_type, "value", a.appointment_type) or ""),
                    }
                    for a in appts
                    if _st(a) != "cancelled"
                ],
                "admissions": [
                    {
                        "id": ad.id,
                        "status": ad.status,
                        "admitted_at": ad.admitted_at.isoformat() if ad.admitted_at else None,
                        "discharged_at": ad.discharged_at.isoformat() if ad.discharged_at else None,
                        "urgency": ad.urgency,
                    }
                    for ad in admissions
                    if ad.status != AdmissionStatus.CANCELLED.value
                ],
            },
        )

    def preview_bill(
        self,
        db: Session,
        patient_id: int,
        discount: float = 0.0,
        tax: float = 0.0,
        include_categories: list[str] | None = None,
        appointment_id: int | None = None,
        admission_id: int | None = None,
        unbilled_only: bool = True,
    ):
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise NotFoundException("Patient not found.")

        items, warnings, skipped = self._collect_charges(
            db, patient,
            appointment_id=appointment_id,
            admission_id=admission_id,
            unbilled_only=unbilled_only,
        )
        if include_categories:
            allowed = {c.lower() for c in include_categories}
            items = [i for i in items if i["category"] in allowed]

        subtotal = round(sum(i["amount"] for i in items), 2)
        discount = max(0.0, float(discount or 0))
        tax = max(0.0, float(tax or 0))
        total = round(max(0.0, subtotal - discount + tax), 2)
        category_totals: dict[str, float] = {}
        for i in items:
            category_totals[i["category"]] = round(
                category_totals.get(i["category"], 0.0) + i["amount"], 2
            )
        if skipped:
            warnings.append(
                f"{skipped} charge line(s) skipped — already on a previous bill."
            )
        return ServiceResult.Success(
            "Bill preview ready.",
            {
                "patient_id": patient.id,
                "patient_name": patient.name,
                "patient_phone": patient.phone,
                "patient_email": patient.email,
                "appointment_id": appointment_id,
                "admission_id": admission_id,
                "items": items,
                "subtotal": subtotal,
                "discount": discount,
                "tax": tax,
                "total": total,
                "currency": "PKR",
                "category_totals": category_totals,
                "warnings": warnings,
                "skipped_already_billed": skipped,
            },
        )

    def create_bill(self, db: Session, data: BillCreateRequest, issued_by: int | None):
        preview = self.preview_bill(
            db,
            data.patient_id,
            discount=data.discount,
            tax=data.tax,
            include_categories=data.include_categories,
            appointment_id=data.appointment_id,
            admission_id=data.admission_id,
            unbilled_only=True if data.unbilled_only is None else data.unbilled_only,
        ).data
        if not preview["items"]:
            raise BadRequestException(
                "No unbilled chargeable services for this scope. "
                "Select another appointment/admission or clear filters."
            )
        bill_number = self._next_bill_number(db)
        with UnitOfWork(db):
            bill = Bill(
                bill_number=bill_number,
                patient_id=preview["patient_id"],
                patient_name=preview["patient_name"],
                patient_phone=preview["patient_phone"],
                patient_email=preview["patient_email"],
                appointment_id=data.appointment_id,
                admission_id=data.admission_id,
                status=BillStatus.ISSUED.value,
                subtotal=preview["subtotal"],
                discount=preview["discount"],
                tax=preview["tax"],
                total=preview["total"],
                currency="PKR",
                notes=data.notes,
                issued_by=issued_by,
                issued_at=datetime.now(timezone.utc),
            )
            db.add(bill)
            db.flush()
            for row in preview["items"]:
                db.add(
                    BillItem(
                        bill_id=bill.id,
                        category=row["category"],
                        description=row["description"],
                        details=row.get("details"),
                        quantity=row["quantity"],
                        unit_price=row["unit_price"],
                        amount=row["amount"],
                        reference_type=row.get("reference_type"),
                        reference_id=row.get("reference_id"),
                    )
                )
                self._mark_source_billed(
                    db, row.get("reference_type"), row.get("reference_id"), bill.id
                )
            db.flush()
            db.refresh(bill)
        enriched = self._enrich_bill(db, bill.id)
        self._notify_patient_bill(db, patient_id=preview["patient_id"], bill=enriched)
        return ServiceResult.Success("Bill issued successfully.", enriched)

    def get_bill(self, db: Session, bill_id: int):
        data = self._enrich_bill(db, bill_id)
        if not data:
            raise NotFoundException("Bill not found.")
        return ServiceResult.Success("OK", data)

    def list_bills(self, db: Session, patient_id: int | None = None, status: str | None = None, limit: int = 50):
        q = db.query(Bill).order_by(Bill.id.desc())
        if patient_id:
            q = q.filter(Bill.patient_id == patient_id)
        if status:
            q = q.filter(Bill.status == status.lower())
        rows = q.limit(limit).all()
        return ServiceResult.Success("OK", [self._enrich_bill(db, b.id) for b in rows])

    def mark_paid(self, db: Session, bill_id: int, data: BillPayRequest):
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise NotFoundException("Bill not found.")
        if bill.status == BillStatus.CANCELLED.value:
            raise ConflictException("Cancelled bills cannot be paid.")
        if bill.status == BillStatus.PAID.value:
            raise ConflictException("Bill is already paid.")
        with UnitOfWork(db):
            bill.status = BillStatus.PAID.value
            bill.payment_method = (data.payment_method or "cash").lower()
            bill.paid_at = datetime.now(timezone.utc)
            if data.notes:
                bill.notes = ((bill.notes + "\n") if bill.notes else "") + data.notes
            db.flush()
        return ServiceResult.Success("Payment recorded.", self._enrich_bill(db, bill_id))

    def cancel_bill(self, db: Session, bill_id: int):
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise NotFoundException("Bill not found.")
        if bill.status == BillStatus.PAID.value:
            raise ConflictException("Paid bills cannot be cancelled.")
        with UnitOfWork(db):
            bill.status = BillStatus.CANCELLED.value
            bill.cancelled_at = datetime.now(timezone.utc)
            for item in bill.items or []:
                self._unmark_source_billed(db, item.reference_type, item.reference_id, bill.id)
            db.flush()
        return ServiceResult.Success("Bill cancelled.", self._enrich_bill(db, bill_id))

    def _billed_refs(self, db: Session, patient_id: int) -> set:
        rows = (
            db.query(BillItem.reference_type, BillItem.reference_id)
            .join(Bill, Bill.id == BillItem.bill_id)
            .filter(
                Bill.patient_id == patient_id,
                Bill.status != BillStatus.CANCELLED.value,
                BillItem.reference_type.isnot(None),
                BillItem.reference_id.isnot(None),
            )
            .all()
        )
        return {(r[0], int(r[1])) for r in rows if r[0] and r[1] is not None}

    def _collect_charges(self, db, patient, appointment_id=None, admission_id=None, unbilled_only=True):
        billed = self._billed_refs(db, patient.id) if unbilled_only else set()
        warnings: list = []
        skipped = 0
        raw: list = []
        raw.extend(self._consultation_items(db, patient, warnings, appointment_id, admission_id))
        raw.extend(self._medicine_items(db, patient, warnings, appointment_id, admission_id))
        raw.extend(self._lab_items(db, patient, warnings, appointment_id, admission_id))
        raw.extend(self._bed_items(db, patient, warnings, admission_id))
        raw.extend(self._nursing_items(db, patient, warnings, admission_id))
        items = []
        for i in raw:
            key = (i.get("reference_type"), i.get("reference_id"))
            if unbilled_only and key[0] and key[1] is not None and key in billed:
                skipped += 1
                continue
            items.append(i)
        return items, warnings, skipped

    def _consultation_items(self, db, patient, warnings, appointment_id, admission_id):
        if admission_id and not appointment_id:
            return []
        q = db.query(Appointment).options(joinedload(Appointment.doctor)).filter(
            Appointment.patient_id == patient.id
        )
        if appointment_id:
            q = q.filter(Appointment.id == appointment_id)
        rows = q.order_by(Appointment.appointment_date.desc()).all()
        items = []
        for appt in rows:
            s = str(getattr(appt.status, "value", appt.status) or "").lower()
            if s == "cancelled":
                continue
            doctor = appt.doctor
            fee = float(doctor.consultation_fee) if doctor and doctor.consultation_fee else DEFAULT_CONSULTATION_FEE
            doc_name = doctor.full_name if doctor else f"Doctor #{appt.doctor_id}"
            appt_type = getattr(appt.appointment_type, "value", str(appt.appointment_type or "physical"))
            date_str = appt.appointment_date.isoformat() if appt.appointment_date else "—"
            time_str = appt.appointment_time.strftime("%H:%M") if appt.appointment_time else ""
            items.append({
                "category": BillItemCategory.CONSULTATION.value,
                "description": f"Doctor consultation — {doc_name}",
                "details": f"{date_str} {time_str} · {appt_type} · Appt #{appt.id}",
                "quantity": 1.0,
                "unit_price": fee,
                "amount": fee,
                "reference_type": "appointment",
                "reference_id": appt.id,
            })
        return items

    def _medicine_items(self, db, patient, warnings, appointment_id, admission_id):
        """Include all dispensed pharmacy lines (OPD Rx + ward course)."""
        rows = (
            db.query(PharmacyOrder)
            .options(joinedload(PharmacyOrder.medicine), joinedload(PharmacyOrder.prescription_item))
            .filter(
                PharmacyOrder.patient_id == patient.id,
                PharmacyOrder.status == PharmacyOrderStatus.DISPENSED.value,
            )
            .order_by(PharmacyOrder.id.desc())
            .all()
        )
        items = []
        for order in rows:
            pi = order.prescription_item
            presc = None
            if pi is not None:
                presc = db.query(Prescription).filter(Prescription.id == pi.prescription_id).first()
            source = (getattr(order, "source", None) or "prescription").lower()
            is_course = source == "course"

            if appointment_id:
                if is_course:
                    continue
                if not presc or presc.appointment_id != appointment_id:
                    continue
            elif admission_id:
                if presc is not None and presc.admission_id and presc.admission_id != admission_id:
                    continue
                if presc is not None and presc.appointment_id and not presc.admission_id and not is_course:
                    continue
                # course / no prescription_item → include on admission bill

            med = order.medicine
            name = med.name if med else (
                (pi.medicine_name if pi else None) or f"Order #{order.id}"
            )
            unit_price = None
            if med is not None:
                try:
                    db.refresh(med)
                except Exception:
                    pass
                if getattr(med, "unit_price", None) is not None:
                    try:
                        unit_price = float(med.unit_price)
                    except (TypeError, ValueError):
                        unit_price = None
            if unit_price is None or unit_price < 0:
                unit_price = float(DEFAULT_MEDICINE_PRICE)
            qty = float(getattr(order, "quantity", None) or 1)
            if qty < 1:
                qty = 1.0
            amount = round(qty * unit_price, 2)
            items.append({
                "category": BillItemCategory.MEDICINE.value,
                "description": f"Medicine — {name}",
                "details": f"Qty {int(qty)} · Order #{order.id}",
                "quantity": qty,
                "unit_price": unit_price,
                "amount": amount,
                "reference_type": "pharmacy_order",
                "reference_id": order.id,
            })
        return items

    def _lab_items(self, db, patient, warnings, appointment_id, admission_id):
        q = (
            db.query(LabOrder)
            .options(joinedload(LabOrder.results).joinedload(LabResult.lab_test))
            .filter(LabOrder.patient_id == patient.id)
        )
        if appointment_id:
            q = q.filter(LabOrder.appointment_id == appointment_id)
        if admission_id:
            q = q.filter(LabOrder.admission_id == admission_id)
        orders = q.order_by(LabOrder.id.desc()).all()
        items = []
        for order in orders:
            results = list(order.results or [])
            if results:
                for res in results:
                    test = res.lab_test
                    name = test.name if test else f"Lab test #{res.lab_test_id}"
                    price = float(test.price) if test and test.price is not None else DEFAULT_LAB_PRICE
                    items.append({
                        "category": BillItemCategory.LAB.value,
                        "description": f"Lab test — {name}",
                        "details": f"Order #{order.id}",
                        "quantity": 1.0,
                        "unit_price": price,
                        "amount": price,
                        "reference_type": "lab_result",
                        "reference_id": res.id,
                    })
            elif str(order.status).lower() in ("completed", "reported"):
                items.append({
                    "category": BillItemCategory.LAB.value,
                    "description": f"Laboratory order #{order.id}",
                    "details": f"Status: {order.status}",
                    "quantity": 1.0,
                    "unit_price": DEFAULT_LAB_PRICE,
                    "amount": DEFAULT_LAB_PRICE,
                    "reference_type": "lab_order",
                    "reference_id": order.id,
                })
        return items

    def _bed_items(self, db, patient, warnings, admission_id):
        q = (
            db.query(Admission)
            .options(joinedload(Admission.bed).joinedload(Bed.ward))
            .filter(
                Admission.patient_id == patient.id,
                Admission.status.in_([AdmissionStatus.ADMITTED.value, AdmissionStatus.DISCHARGED.value]),
            )
        )
        if admission_id:
            q = q.filter(Admission.id == admission_id)
        items = []
        for adm in q.order_by(Admission.id.desc()).all():
            if not adm.admitted_at:
                continue
            start = adm.admitted_at
            end = adm.discharged_at or datetime.now(timezone.utc)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            nights = max(1, ceil((end - start).total_seconds() / 86400.0))
            ward = adm.bed.ward if adm.bed and getattr(adm.bed, "ward", None) else None
            ward_type = (ward.type if ward else getattr(adm, "preferred_ward_type", None) or "general")
            ward_type = str(ward_type).lower()
            rate = None
            if ward is not None:
                # refresh from DB so edited daily_rate is not a stale identity value
                try:
                    db.refresh(ward)
                except Exception:
                    pass
                raw = getattr(ward, "daily_rate", None)
                if raw is not None:
                    try:
                        rate = float(raw)
                    except (TypeError, ValueError):
                        rate = None
            if rate is None or rate <= 0:
                rate = float(DEFAULT_BED_RATES.get(ward_type, DEFAULT_BED_RATES["general"]))
            bed_label = f"Bed {adm.bed.bed_number}" if adm.bed else ward_type
            if ward and adm.bed:
                bed_label = f"{ward.name} — Bed {adm.bed.bed_number}"
            items.append({
                "category": BillItemCategory.BED.value,
                "description": f"Bed / ward charges — {bed_label}",
                "details": f"Admission #{adm.id} · {nights} night(s) @ PKR {rate:.0f}",
                "quantity": float(nights),
                "unit_price": rate,
                "amount": round(nights * rate, 2),
                "reference_type": "admission_bed",
                "reference_id": adm.id,
            })
        return items

    def _nursing_items(self, db, patient, warnings, admission_id):
        items = []
        adm_q = db.query(Admission.id).filter(Admission.patient_id == patient.id)
        if admission_id:
            adm_q = adm_q.filter(Admission.id == admission_id)
        adm_ids = [r[0] for r in adm_q.all()]
        if not adm_ids:
            return items
        doses = (
            db.query(MedicationCourseDose)
            .options(joinedload(MedicationCourseDose.item))
            .filter(
                MedicationCourseDose.admission_id.in_(adm_ids),
                MedicationCourseDose.status == "given",
            )
            .all()
        )
        for dose in doses:
            med_name = dose.item.medicine_name if dose.item else "Medication"
            items.append({
                "category": BillItemCategory.NURSING.value,
                "description": f"Nursing — dose ({med_name})",
                "details": f"Dose #{dose.id}",
                "quantity": 1.0,
                "unit_price": DEFAULT_NURSING_PER_DOSE,
                "amount": DEFAULT_NURSING_PER_DOSE,
                "reference_type": "dose",
                "reference_id": dose.id,
            })
        admissions = (
            db.query(Admission)
            .filter(
                Admission.id.in_(adm_ids),
                Admission.status.in_([AdmissionStatus.ADMITTED.value, AdmissionStatus.DISCHARGED.value]),
                Admission.admitted_at.isnot(None),
            )
            .all()
        )
        for adm in admissions:
            start = adm.admitted_at
            end = adm.discharged_at or datetime.now(timezone.utc)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            days = max(1, ceil((end - start).total_seconds() / 86400.0))
            items.append({
                "category": BillItemCategory.NURSING.value,
                "description": "Nursing care (daily)",
                "details": f"Admission #{adm.id} · {days} day(s)",
                "quantity": float(days),
                "unit_price": DEFAULT_NURSING_PER_DAY,
                "amount": round(days * DEFAULT_NURSING_PER_DAY, 2),
                "reference_type": "admission_nursing",
                "reference_id": adm.id,
            })
        return items

    def _mark_source_billed(self, db, ref_type, ref_id, bill_id):
        if not ref_type or ref_id is None:
            return
        if ref_type == "pharmacy_order":
            row = db.query(PharmacyOrder).filter(PharmacyOrder.id == ref_id).first()
            if row is not None and hasattr(row, "bill_id"):
                row.bill_id = bill_id
        elif ref_type == "lab_order":
            row = db.query(LabOrder).filter(LabOrder.id == ref_id).first()
            if row is not None and hasattr(row, "bill_id"):
                row.bill_id = bill_id
        elif ref_type == "lab_result":
            res = db.query(LabResult).filter(LabResult.id == ref_id).first()
            if res:
                order = db.query(LabOrder).filter(LabOrder.id == res.lab_order_id).first()
                if order is not None and hasattr(order, "bill_id"):
                    order.bill_id = bill_id

    def _unmark_source_billed(self, db, ref_type, ref_id, bill_id):
        if not ref_type or ref_id is None:
            return
        if ref_type == "pharmacy_order":
            row = db.query(PharmacyOrder).filter(PharmacyOrder.id == ref_id).first()
            if row is not None and getattr(row, "bill_id", None) == bill_id:
                row.bill_id = None
        elif ref_type in ("lab_order", "lab_result"):
            if ref_type == "lab_order":
                row = db.query(LabOrder).filter(LabOrder.id == ref_id).first()
            else:
                res = db.query(LabResult).filter(LabResult.id == ref_id).first()
                row = db.query(LabOrder).filter(LabOrder.id == res.lab_order_id).first() if res else None
            if row is not None and getattr(row, "bill_id", None) == bill_id:
                row.bill_id = None

    def _notify_patient_bill(self, db, patient_id, bill):
        try:
            from app.services.firebase_service import send_notification
            from app.models.user import User
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                return
            title = "New bill from Lumina Health"
            total = (bill or {}).get("total")
            bill_number = (bill or {}).get("bill_number") or ""
            body = f"Bill {bill_number} issued. Total due: PKR {float(total or 0):,.0f}."
            data = {
                "type": "bill_issued",
                "bill_id": str((bill or {}).get("id") or ""),
                "bill_number": str(bill_number),
                "total": str(total or 0),
                "patient_id": str(patient_id),
            }
            tokens = set()
            if getattr(patient, "fcm_token", None):
                tokens.add(patient.fcm_token)
            if patient.user_id:
                user = db.query(User).filter(User.id == patient.user_id).first()
                if user and getattr(user, "fcm_token", None):
                    tokens.add(user.fcm_token)
            for token in tokens:
                try:
                    send_notification(token=token, title=title, body=body, data=data)
                except Exception:
                    pass
        except Exception as e:
            import logging
            logging.getLogger("ClinicAI").warning(f"Bill notification failed: {e}")

    def _next_bill_number(self, db: Session) -> str:
        today = date.today().strftime("%Y%m%d")
        prefix = f"BILL-{today}-"
        last = (
            db.query(Bill)
            .filter(Bill.bill_number.like(f"{prefix}%"))
            .order_by(Bill.id.desc())
            .first()
        )
        seq = 1
        if last and last.bill_number:
            try:
                seq = int(last.bill_number.rsplit("-", 1)[-1]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{seq:04d}"

    def _enrich_bill(self, db: Session, bill_id: int):
        bill = db.query(Bill).options(joinedload(Bill.items)).filter(Bill.id == bill_id).first()
        if not bill:
            return None
        items = [
            {
                "id": i.id,
                "category": i.category,
                "description": i.description,
                "details": i.details,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "amount": i.amount,
                "reference_type": i.reference_type,
                "reference_id": i.reference_id,
            }
            for i in (bill.items or [])
        ]
        category_totals = {}
        for i in items:
            category_totals[i["category"]] = round(
                category_totals.get(i["category"], 0.0) + float(i["amount"]), 2
            )
        return {
            "id": bill.id,
            "bill_number": bill.bill_number,
            "patient_id": bill.patient_id,
            "patient_name": bill.patient_name,
            "patient_phone": bill.patient_phone,
            "patient_email": bill.patient_email,
            "appointment_id": getattr(bill, "appointment_id", None),
            "admission_id": getattr(bill, "admission_id", None),
            "status": bill.status,
            "subtotal": bill.subtotal,
            "discount": bill.discount,
            "tax": bill.tax,
            "total": bill.total,
            "currency": bill.currency,
            "notes": bill.notes,
            "payment_method": bill.payment_method,
            "issued_by": bill.issued_by,
            "issued_at": bill.issued_at,
            "paid_at": bill.paid_at,
            "items": items,
            "category_totals": category_totals,
        }

    # ── Service pricing (admin fee schedule) ─────────────────
    DEFAULT_SERVICE_PRICES = [
        {"key": "nursing_per_dose", "label": "Nursing charge per dose", "amount": 50.0,
         "description": "Charged per medication dose administered by nursing"},
        {"key": "nursing_per_day", "label": "Nursing charge per day", "amount": 200.0,
         "description": "Daily nursing care fee for admitted patients"},
        {"key": "hospital_service_fee", "label": "Hospital service fee", "amount": 100.0,
         "description": "General hospital service / misc fee"},
        {"key": "default_consultation_fee", "label": "Default consultation fee", "amount": 500.0,
         "description": "Fallback OPD consultation fee when doctor fee is missing"},
    ]

    def list_service_pricing(self, db: Session):
        from app.models.service_pricing import ServicePricing
        from app.core.unit_of_work import UnitOfWork
        rows = db.query(ServicePricing).order_by(ServicePricing.key).all()
        existing = {r.key for r in rows}
        missing = [d for d in self.DEFAULT_SERVICE_PRICES if d["key"] not in existing]
        if missing:
            with UnitOfWork(db):
                for d in missing:
                    db.add(ServicePricing(
                        key=d["key"], label=d["label"], amount=d["amount"],
                        description=d.get("description"),
                    ))
            rows = db.query(ServicePricing).order_by(ServicePricing.key).all()
        data = [
            {
                "key": r.key,
                "label": r.label,
                "amount": float(r.amount or 0),
                "description": r.description,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
        return ServiceResult.Success("Service pricing loaded.", data)

    def update_service_pricing(self, db: Session, key: str, data):
        from app.models.service_pricing import ServicePricing
        from app.core.unit_of_work import UnitOfWork
        from app.exceptions.exceptions import NotFoundException
        row = db.query(ServicePricing).filter(ServicePricing.key == key).first()
        if not row:
            raise NotFoundException(f"Service pricing key '{key}' not found.")
        with UnitOfWork(db):
            row.amount = float(data.amount)
            if getattr(data, "label", None):
                row.label = data.label
            if getattr(data, "description", None) is not None:
                row.description = data.description
            db.add(row)
        return ServiceResult.Success(
            "Service pricing updated.",
            {
                "key": row.key,
                "label": row.label,
                "amount": float(row.amount or 0),
                "description": row.description,
                "updated_at": row.updated_at,
            },
        )

