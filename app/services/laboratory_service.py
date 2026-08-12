from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.common.enums import LabOrderStatus
from app.common.messages import Messages
from app.common.service_result import ServiceResult

from app.core.logger import logger
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    BadRequestException,
    ConflictException,
)

from app.models.lab_test import LabTest
from app.models.lab_order import LabOrder
from app.models.lab_result import LabResult

from app.schemas.laboratory import (
    LabTestCreate,
    LabTestUpdate,
    LabOrderCreate,
    LabResultEnter,
)


class LaboratoryService:

    def __init__(
        self,
        lab_test_repository,
        lab_order_repository,
        lab_result_repository,
        patient_repository,
        doctor_repository=None,
        admission_repository=None,
        user_repository=None,
        notification_service=None,
        patient_report_repository=None,
    ):
        self.test_repo = lab_test_repository
        self.order_repo = lab_order_repository
        self.result_repo = lab_result_repository
        self.patient_repo = patient_repository
        self.doctor_repo = doctor_repository
        self.admission_repo = admission_repository
        self.user_repo = user_repository
        self.notification_service = notification_service
        self.report_repo = patient_report_repository

    # ═════════════════════════════════════════════════════
    # Lab Test Catalog
    # ═════════════════════════════════════════════════════
    def create_test(self, db: Session, data: LabTestCreate) -> ServiceResult:
        existing = self.test_repo.get_by_name(db, data.name)
        if existing:
            raise ConflictException(f"Lab test '{data.name}' already exists.")

        if data.code:
            by_code = self.test_repo.get_by_code(db, data.code)
            if by_code:
                raise ConflictException(f"Lab test code '{data.code}' already exists.")

        test = LabTest(
            name=data.name.strip(),
            code=data.code.strip() if data.code else None,
            category=data.category.value if hasattr(data.category, "value") else data.category,
            sample_type=data.sample_type.value if hasattr(data.sample_type, "value") else data.sample_type,
            description=data.description,
            unit=data.unit,
            normal_range_min=data.normal_range_min,
            normal_range_max=data.normal_range_max,
            normal_range_text=data.normal_range_text,
            price=data.price or 0.0,
            turnaround_hours=data.turnaround_hours or 24,
            is_active=data.is_active,
        )
        with UnitOfWork(db):
            test = self.test_repo.create(db, test)
        return ServiceResult.Success("Lab test created.", test)

    def list_tests(self, db: Session, active_only: bool = False) -> ServiceResult:
        tests = self.test_repo.get_all(db, active_only=active_only)
        return ServiceResult.Success(Messages.SUCCESS, tests)

    def get_test(self, db: Session, test_id: int) -> ServiceResult:
        test = self.test_repo.get_by_id(db, test_id)
        if not test:
            raise NotFoundException("Lab test not found.")
        return ServiceResult.Success(Messages.SUCCESS, test)

    def update_test(self, db: Session, test_id: int, data: LabTestUpdate) -> ServiceResult:
        test = self.test_repo.get_by_id(db, test_id)
        if not test:
            raise NotFoundException("Lab test not found.")

        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            if hasattr(value, "value"):
                value = value.value
            setattr(test, key, value)

        with UnitOfWork(db):
            test = self.test_repo.update(db, test)
        return ServiceResult.Success("Lab test updated.", test)

    # ═════════════════════════════════════════════════════
    # Create Lab Order
    # ═════════════════════════════════════════════════════
    def create_order(self, db: Session, data: LabOrderCreate) -> ServiceResult:
        patient = self.patient_repo.get_by_id(db, data.patient_id)
        if not patient:
            raise NotFoundException(Messages.PATIENT_NOT_FOUND)

        tests = []
        for tid in data.test_ids:
            t = self.test_repo.get_by_id(db, tid)
            if not t or not t.is_active:
                raise BadRequestException(f"Lab test id={tid} not found or inactive.")
            tests.append(t)

        order = LabOrder(
            patient_id=data.patient_id,
            ordered_by_doctor_id=data.ordered_by_doctor_id,
            appointment_id=data.appointment_id,
            admission_id=data.admission_id,
            prescription_id=data.prescription_id,
            status=LabOrderStatus.PENDING.value,
            priority=data.priority or "routine",
            clinical_notes=data.clinical_notes,
        )

        with UnitOfWork(db):
            order = self.order_repo.create(db, order)
            results = [
                LabResult(
                    lab_order_id=order.id,
                    lab_test_id=t.id,
                    unit=t.unit,
                    status="pending",
                )
                for t in tests
            ]
            self.result_repo.create_many(db, results)

        # Reload with relationships
        order = self.order_repo.get_by_id(db, order.id)
        self._notify_role(db, role="lab_technician", title="New Lab Order",
                          body=f"New lab order #{order.id} for {patient.name}")

        return ServiceResult.Success("Lab order created.", self._enrich_order(order))

    # ═════════════════════════════════════════════════════
    # Queue / List / Get
    # ═════════════════════════════════════════════════════

    def create_walk_in_order(self, db: Session, data) -> ServiceResult:
        """Counter lab order — patient walks in without a doctor order."""
        from app.schemas.laboratory import WalkInLabOrderCreate

        name = (getattr(data, "customer_name", None) or "").strip()
        phone = (getattr(data, "customer_phone", None) or "").strip()
        patient_id = getattr(data, "patient_id", None)

        if patient_id:
            patient = self.patient_repo.get_by_id(db, patient_id)
            if not patient:
                raise NotFoundException(Messages.PATIENT_NOT_FOUND)
            if not name:
                name = getattr(patient, "name", None) or f"Patient #{patient_id}"
        elif not name:
            raise BadRequestException(
                "Provide a customer name or select a registered patient."
            )

        tests = []
        for tid in data.test_ids:
            t = self.test_repo.get_by_id(db, tid)
            if not t or not t.is_active:
                raise BadRequestException(f"Lab test id={tid} not found or inactive.")
            tests.append(t)

        doctor_id = getattr(data, "ordered_by_doctor_id", None)
        if doctor_id:
            # soft-validate doctor exists if repo available
            pass

        order = LabOrder(
            patient_id=patient_id,
            ordered_by_doctor_id=doctor_id,
            appointment_id=None,
            admission_id=None,
            prescription_id=None,
            status=LabOrderStatus.PENDING.value,
            priority=data.priority or "routine",
            clinical_notes=data.clinical_notes,
            order_source="walk_in",
            customer_name=name or None,
            customer_phone=phone or None,
        )

        with UnitOfWork(db):
            order = self.order_repo.create(db, order)
            results = [
                LabResult(
                    lab_order_id=order.id,
                    lab_test_id=t.id,
                    unit=t.unit,
                    status="pending",
                )
                for t in tests
            ]
            self.result_repo.create_many(db, results)

        order = self.order_repo.get_by_id(db, order.id)
        self._notify_role(
            db,
            role="lab_technician",
            title="Walk-in Lab Order",
            body=f"Walk-in lab order #{order.id} for {name}",
        )
        return ServiceResult.Success("Walk-in lab order created.", self._enrich_order(order))


    def get_queue(self, db: Session) -> ServiceResult:
        orders = self.order_repo.get_pending_queue(db)
        return ServiceResult.Success(Messages.SUCCESS, [self._enrich_order(o) for o in orders])

    def list_orders(self, db: Session, status: str | None = None) -> ServiceResult:
        orders = self.order_repo.get_all(db, status=status)
        return ServiceResult.Success(Messages.SUCCESS, [self._enrich_order(o) for o in orders])

    def get_order(self, db: Session, order_id: int) -> ServiceResult:
        order = self.order_repo.get_by_id(db, order_id)
        if not order:
            raise NotFoundException("Lab order not found.")
        return ServiceResult.Success(Messages.SUCCESS, self._enrich_order(order))

    def get_patient_orders(self, db: Session, patient_id: int) -> ServiceResult:
        orders = self.order_repo.get_by_patient(db, patient_id)
        return ServiceResult.Success(Messages.SUCCESS, [self._enrich_order(o) for o in orders])

    # ═════════════════════════════════════════════════════
    # Sample Collection
    # ═════════════════════════════════════════════════════
    def collect_sample(
        self,
        db: Session,
        order_id: int,
        collected_by_username: str | None,
    ) -> ServiceResult:
        order = self.order_repo.get_by_id(db, order_id)
        if not order:
            raise NotFoundException("Lab order not found.")

        if order.status != LabOrderStatus.PENDING.value:
            raise ConflictException(
                f"Cannot collect sample — order is already '{order.status}'."
            )

        user_id = None
        if collected_by_username and self.user_repo:
            user = self.user_repo.get_by_username(db, collected_by_username)
            if user:
                user_id = user.id

        order.status = LabOrderStatus.SAMPLE_COLLECTED.value
        order.sample_collected_at = datetime.now(timezone.utc)
        order.sample_collected_by = user_id

        with UnitOfWork(db):
            self.order_repo.update(db, order)

        return ServiceResult.Success("Sample collected.", self._enrich_order(order))

    # ═════════════════════════════════════════════════════
    # Enter / Verify Results
    # ═════════════════════════════════════════════════════
    def enter_result(
        self,
        db: Session,
        result_id: int,
        data: LabResultEnter,
        entered_by_username: str | None,
    ) -> ServiceResult:
        result = self.result_repo.get_by_id(db, result_id)
        if not result:
            raise NotFoundException("Lab result not found.")

        order = self.order_repo.get_by_id(db, result.lab_order_id)
        if not order:
            raise NotFoundException("Lab order not found.")

        if order.status in (LabOrderStatus.CANCELLED.value, LabOrderStatus.COMPLETED.value):
            raise ConflictException(f"Cannot enter results — order is '{order.status}'.")

        user_id = None
        if entered_by_username and self.user_repo:
            user = self.user_repo.get_by_username(db, entered_by_username)
            if user:
                user_id = user.id

        result.value_numeric = data.value_numeric
        result.value_text = data.value_text
        if data.unit is not None:
            result.unit = data.unit
        result.is_abnormal = data.is_abnormal
        result.remarks = data.remarks
        result.status = "entered"
        result.entered_by = user_id
        result.entered_at = datetime.now(timezone.utc)

        # Auto-flag abnormal from normal range if numeric
        if (
            result.value_numeric is not None
            and result.lab_test
            and result.lab_test.normal_range_min is not None
            and result.lab_test.normal_range_max is not None
        ):
            if (
                result.value_numeric < result.lab_test.normal_range_min
                or result.value_numeric > result.lab_test.normal_range_max
            ):
                result.is_abnormal = True

        # Move order to processing if still at sample_collected
        if order.status == LabOrderStatus.SAMPLE_COLLECTED.value:
            order.status = LabOrderStatus.PROCESSING.value

        with UnitOfWork(db):
            self.result_repo.update(db, result)
            self.order_repo.update(db, order)

        return ServiceResult.Success("Result entered.", self._enrich_result(result))

    def complete_order(
        self,
        db: Session,
        order_id: int,
        reported_by_username: str | None,
    ) -> ServiceResult:
        order = self.order_repo.get_by_id(db, order_id)
        if not order:
            raise NotFoundException("Lab order not found.")

        if order.status == LabOrderStatus.COMPLETED.value:
            raise ConflictException("Order already completed.")
        if order.status == LabOrderStatus.CANCELLED.value:
            raise ConflictException("Cannot complete a cancelled order.")

        # All results should be entered
        pending = [r for r in order.results if r.status == "pending"]
        if pending:
            raise BadRequestException(
                f"{len(pending)} result(s) still pending. Enter all results first."
            )

        user_id = None
        if reported_by_username and self.user_repo:
            user = self.user_repo.get_by_username(db, reported_by_username)
            if user:
                user_id = user.id

        order.status = LabOrderStatus.COMPLETED.value
        order.completed_at = datetime.now(timezone.utc)
        order.reported_by = user_id

        for r in order.results:
            if r.status == "entered":
                r.status = "verified"
                r.verified_by = user_id
                r.verified_at = datetime.now(timezone.utc)

        emr_report = None
        with UnitOfWork(db):
            self.order_repo.update(db, order)
            for r in order.results:
                self.result_repo.update(db, r)

            # Generate formal lab report and save into patient EMR
            try:
                emr_report = self._save_report_to_emr(db, order)
            except Exception as e:
                logger.error(f"Failed to save lab report to EMR for order {order.id}: {e}")

        # Notify patient / doctor that results are ready
        patient_name = order.patient.name if order.patient else f"Patient #{order.patient_id}"
        self._notify_role(
            db,
            role="doctor",
            title="Lab Results Ready",
            body=f"Lab order #{order.id} results for {patient_name} are ready.",
        )
        try:
            from app.services.firebase_service import send_notification
            token = getattr(order.patient, "fcm_token", None) if order.patient else None
            if token:
                send_notification(
                    token,
                    title="Your Lab Results are Ready",
                    body=f"Results for lab order #{order.id} are now available in your medical record.",
                )
        except Exception as e:
            logger.warning(f"Could not push patient lab notification: {e}")

        enriched = self._enrich_order(order)
        if emr_report is not None:
            enriched.emr_report_id = getattr(emr_report, "id", None)
            enriched.emr_report_path = getattr(emr_report, "file_path", None)
        return ServiceResult.Success("Lab order completed. Report saved to patient EMR.", enriched)

    def cancel_order(self, db: Session, order_id: int) -> ServiceResult:
        order = self.order_repo.get_by_id(db, order_id)
        if not order:
            raise NotFoundException("Lab order not found.")
        if order.status == LabOrderStatus.COMPLETED.value:
            raise ConflictException("Cannot cancel a completed order.")
        if order.status == LabOrderStatus.CANCELLED.value:
            raise ConflictException("Order is already cancelled.")

        order.status = LabOrderStatus.CANCELLED.value
        with UnitOfWork(db):
            self.order_repo.update(db, order)

        patient_name = order.patient.name if getattr(order, "patient", None) else f"Patient #{order.patient_id}"
        body = (
            f"Lab order #{order_id} for {patient_name} was cancelled by the laboratory. "
            f"It will not stay pending — submit a new order if tests are still required."
        )
        self._notify_role(db, role="doctor", title="Lab order cancelled", body=body)
        try:
            from app.services.firebase_service import send_notification
            token = getattr(order.patient, "fcm_token", None) if getattr(order, "patient", None) else None
            if token:
                send_notification(token=token, title="Lab order cancelled", body=body)
            # ordering doctor directly if available
            doc = getattr(order, "ordered_by_doctor", None)
            if doc and getattr(doc, "fcm_token", None):
                send_notification(token=doc.fcm_token, title="Lab order cancelled", body=body)
        except Exception:
            pass

        return ServiceResult.Success("Lab order cancelled.", self._enrich_order(order))

    # ═════════════════════════════════════════════════════
    # Helpers
    # ═════════════════════════════════════════════════════
    def _enrich_order(self, order: LabOrder):
        if order.patient:
            order.patient_name = order.patient.name
        elif getattr(order, "customer_name", None):
            order.patient_name = order.customer_name
        if order.ordered_by_doctor:
            order.doctor_name = order.ordered_by_doctor.full_name
        else:
            order.doctor_name = "Walk-in (no doctor)"

        if getattr(order, "order_source", None) == "walk_in":
            order.source = "walk_in"
        else:
            order.source = "ipd" if order.admission_id else "opd"
        order.ward_bed_label = None
        if order.admission and getattr(order.admission, "bed", None):
            bed = order.admission.bed
            ward_name = bed.ward.name if getattr(bed, "ward", None) else "Ward"
            order.ward_bed_label = f"{ward_name} — Bed {bed.bed_number}"

        for r in order.results or []:
            self._enrich_result(r)
        return order

    def _enrich_result(self, result: LabResult):
        if result.lab_test:
            result.test_name = result.lab_test.name
            result.test_code = result.lab_test.code
            result.sample_type = result.lab_test.sample_type
            if result.lab_test.normal_range_text:
                result.normal_range_text = result.lab_test.normal_range_text
            elif (
                result.lab_test.normal_range_min is not None
                and result.lab_test.normal_range_max is not None
            ):
                result.normal_range_text = (
                    f"{result.lab_test.normal_range_min} – {result.lab_test.normal_range_max}"
                )
        return result


    # ═════════════════════════════════════════════════════
    # Formal lab report → patient EMR
    # ═════════════════════════════════════════════════════
    def _save_report_to_emr(self, db: Session, order: LabOrder):
        """Build a formal HTML lab report, write it to disk, and create a
        PatientReport so it appears in the patient's medical record."""
        import os
        import uuid
        from app.models.patient_report import PatientReport
        from app.common.enums import ReportType

        html = self._build_report_html(order)

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        upload_dir = os.path.join(base_dir, "uploads", "reports")
        os.makedirs(upload_dir, exist_ok=True)

        unique_name = f"lab_order_{order.id}_{uuid.uuid4().hex[:10]}.html"
        abs_path = os.path.join(upload_dir, unique_name)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(html)

        relative_path = f"uploads/reports/{unique_name}"

        # Choose report_type from the tests on the order
        report_type = ReportType.OTHER.value
        categories = {
            (r.lab_test.category if r.lab_test else "") for r in (order.results or [])
        }
        if "hematology" in categories or "biochemistry" in categories or "serology" in categories:
            report_type = ReportType.BLOOD_TEST.value

        test_names = [
            (r.lab_test.name if r.lab_test else f"Test #{r.lab_test_id}")
            for r in (order.results or [])
        ]
        report_name = f"Lab Report #{order.id}"
        if test_names:
            short = ", ".join(test_names[:3])
            if len(test_names) > 3:
                short += f" +{len(test_names) - 3} more"
            report_name = f"Lab Report #{order.id}: {short}"

        record = PatientReport(
            patient_id=order.patient_id,
            appointment_id=order.appointment_id,
            doctor_id=order.ordered_by_doctor_id,
            report_name=report_name[:200],
            report_type=report_type,
            file_path=relative_path,
        )

        if self.report_repo:
            created = self.report_repo.create(db, record)
        else:
            db.add(record)
            db.flush()
            db.refresh(record)
            created = record

        logger.info(
            f"Lab report saved to EMR | Order={order.id} | "
            f"Patient={order.patient_id} | File={relative_path}"
        )
        return created

    def _build_report_html(self, order: LabOrder) -> str:
        """Professional printable laboratory result report."""
        from datetime import datetime, timezone
        from html import escape

        patient = order.patient
        doctor = order.ordered_by_doctor
        patient_name = escape(patient.name if patient else f"Patient #{order.patient_id}")
        patient_phone = escape(getattr(patient, "phone", None) or "—")
        doctor_name = escape(doctor.full_name if doctor else str(order.ordered_by_doctor_id))
        ordered_at = order.created_at.strftime("%d %b %Y, %H:%M") if order.created_at else "—"
        completed_at = (
            order.completed_at.strftime("%d %b %Y, %H:%M")
            if order.completed_at
            else datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M")
        )
        sample_at = (
            order.sample_collected_at.strftime("%d %b %Y, %H:%M")
            if order.sample_collected_at
            else "—"
        )
        priority = escape((order.priority or "routine").upper())
        notes = escape(order.clinical_notes or "—")
        source = "IPD" if order.admission_id else "OPD"
        ward = ""
        if order.admission and getattr(order.admission, "bed", None):
            bed = order.admission.bed
            ward_name = bed.ward.name if getattr(bed, "ward", None) else "Ward"
            ward = f"{ward_name} — Bed {bed.bed_number}"

        rows = []
        for r in order.results or []:
            test_name = escape(r.lab_test.name if r.lab_test else f"Test #{r.lab_test_id}")
            code = escape((r.lab_test.code if r.lab_test and r.lab_test.code else "") or "")
            unit = escape(r.unit or (r.lab_test.unit if r.lab_test else "") or "")
            if r.value_numeric is not None:
                value = escape(str(r.value_numeric))
            else:
                value = escape(r.value_text or "—")
            if r.lab_test and r.lab_test.normal_range_text:
                ref = escape(r.lab_test.normal_range_text)
            elif r.lab_test and r.lab_test.normal_range_min is not None and r.lab_test.normal_range_max is not None:
                ref = escape(f"{r.lab_test.normal_range_min} – {r.lab_test.normal_range_max}")
            else:
                ref = "—"
            flag = "H / L" if r.is_abnormal else "Normal"
            flag_class = "abnormal" if r.is_abnormal else "normal"
            remarks = escape(r.remarks or "")
            rows.append(
                f"""<tr class="{flag_class}">
                  <td><strong>{test_name}</strong>{f'<div class="code">{code}</div>' if code else ''}</td>
                  <td class="val">{value}</td>
                  <td>{unit or '—'}</td>
                  <td>{ref}</td>
                  <td><span class="flag {flag_class}">{flag}</span></td>
                  <td>{remarks or '—'}</td>
                </tr>"""
            )

        rows_html = "\n".join(rows) if rows else "<tr><td colspan='6'>No results</td></tr>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Lab Report #{order.id} — {patient_name}</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    color: #1c201a; margin: 0; padding: 24px; background: #fff;
    font-size: 13px; line-height: 1.45;
  }}
  .sheet {{ max-width: 800px; margin: 0 auto; border: 1px solid #d4d8d0; border-radius: 12px; overflow: hidden; }}
  .header {{
    background: linear-gradient(135deg, #3d5a40 0%, #6c8560 100%);
    color: #fff; padding: 22px 28px;
    display: flex; justify-content: space-between; gap: 16px; align-items: flex-start;
  }}
  .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.02em; }}
  .header .sub {{ opacity: 0.9; font-size: 12px; margin-top: 4px; }}
  .badge {{
    display: inline-block; background: rgba(255,255,255,0.18);
    padding: 6px 12px; border-radius: 999px; font-size: 11px; font-weight: 600;
  }}
  .meta {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px;
    padding: 18px 28px; background: #f6f7f4; border-bottom: 1px solid #e4e8e0;
  }}
  .meta .label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7265; }}
  .meta .value {{ font-weight: 600; margin-top: 2px; }}
  .section-title {{
    padding: 14px 28px 6px; font-size: 12px; text-transform: uppercase;
    letter-spacing: 0.08em; color: #6b7265; font-weight: 700;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
    color: #6b7265; padding: 10px 12px; border-bottom: 2px solid #d4d8d0; background: #fafbf8;
  }}
  td {{ padding: 12px; border-bottom: 1px solid #ecefe8; vertical-align: top; }}
  td .code {{ font-size: 11px; color: #6b7265; margin-top: 2px; }}
  td.val {{ font-weight: 700; font-size: 14px; }}
  tr.abnormal {{ background: #fdf6f4; }}
  .flag {{
    display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600;
  }}
  .flag.normal {{ background: #e7f0e4; color: #3d5a40; }}
  .flag.abnormal {{ background: #f5d8d0; color: #8b3a2b; }}
  .notes {{ padding: 12px 28px 20px; font-size: 12px; color: #4a5248; }}
  .footer {{
    padding: 16px 28px; border-top: 1px solid #e4e8e0; font-size: 11px; color: #6b7265;
    display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  }}
  .actions {{ text-align: center; margin: 18px 0; }}
  .actions button {{
    background: #3d5a40; color: #fff; border: 0; padding: 10px 20px; border-radius: 999px;
    font-weight: 600; cursor: pointer;
  }}
  @media print {{
    body {{ padding: 0; }}
    .sheet {{ border: none; border-radius: 0; }}
    .actions {{ display: none; }}
  }}
</style>
</head>
<body>
  <div class="actions"><button onclick="window.print()">Print / Save as PDF</button></div>
  <div class="sheet">
    <div class="header">
      <div>
        <h1>Laboratory Result Report</h1>
        <div class="sub">Lumina Health · Order #{order.id}</div>
      </div>
      <div><span class="badge">{priority} · {source}</span></div>
    </div>
    <div class="meta">
      <div><div class="label">Patient</div><div class="value">{patient_name}</div></div>
      <div><div class="label">Phone</div><div class="value">{patient_phone}</div></div>
      <div><div class="label">Ordering Doctor</div><div class="value">Dr. {doctor_name}</div></div>
      <div><div class="label">Priority</div><div class="value">{priority}</div></div>
      <div><div class="label">Ordered</div><div class="value">{ordered_at}</div></div>
      <div><div class="label">Sample Collected</div><div class="value">{sample_at}</div></div>
      <div><div class="label">Reported</div><div class="value">{completed_at}</div></div>
      <div><div class="label">Location</div><div class="value">{escape(ward) if ward else source}</div></div>
    </div>
    <div class="section-title">Test Results</div>
    <table>
      <thead>
        <tr>
          <th>Test</th><th>Result</th><th>Unit</th><th>Reference Range</th><th>Flag</th><th>Remarks</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
    <div class="notes"><strong>Clinical notes:</strong> {notes}</div>
    <div class="footer">
      <div>This report is part of the patient's official electronic medical record (EMR).</div>
      <div>Generated {datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")}</div>
    </div>
  </div>
</body>
</html>
"""

    def get_report_html(self, db: Session, order_id: int) -> ServiceResult:
        """Return HTML report for a completed order (regenerates if file missing)."""
        order = self.order_repo.get_by_id(db, order_id)
        if not order:
            raise NotFoundException("Lab order not found.")
        if order.status != LabOrderStatus.COMPLETED.value:
            raise BadRequestException("Report is only available for completed orders.")
        html = self._build_report_html(order)
        return ServiceResult.Success(Messages.SUCCESS, {"html": html, "order_id": order_id})


    def _notify_role(self, db: Session, role: str, title: str, body: str):
        """Best-effort FCM notify to all users of a given staff role."""
        if not self.user_repo:
            return
        try:
            from app.services.firebase_service import send_notification
            users = self.user_repo.get_by_role(db, role) if hasattr(self.user_repo, "get_by_role") else []
            for u in users or []:
                token = getattr(u, "fcm_token", None)
                if token:
                    send_notification(token, title=title, body=body)
        except Exception as e:
            logger.warning(f"Lab role notification failed ({role}): {e}")
