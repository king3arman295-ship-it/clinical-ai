from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone, time

from sqlalchemy.orm import Session

from app.core.unit_of_work import UnitOfWork
from app.common.service_result import ServiceResult
from app.exceptions.exceptions import (
    NotFoundException,
    BadRequestException,
    ConflictException,
)
from app.models.nurse_bed_assignment import NurseBedAssignment
from app.models.medication_course import (
    MedicationCourse,
    MedicationCourseItem,
    MedicationCourseDose,
)
from app.models.medication_administration import MedicationAdministration
from app.models.admission import Admission
from app.common.enums import AdmissionStatus
from app.schemas.nursing import (
    NurseBedAssignRequest,
    MedicationCourseCreate,
    MedicationCourseUpdate,
    DoseActionRequest,
)

logger = logging.getLogger("ClinicAI")

FREQ_TIMES = {
    "OD": 1,
    "QD": 1,
    "ONCE": 1,
    "STAT": 1,
    "BD": 2,
    "BID": 2,
    "TID": 3,
    "TDS": 3,
    "QID": 4,
    "QDS": 4,
}


def units_from_dosage(dosage) -> int:
    """Inventory units consumed by ONE dose (not strength in mg).

    Stock is counted in tablets / capsules / vials / bottles:
      "1" / "1 tablet" / "2 tab" → 1 or 2
      "500mg" / "500 mg" / "5ml" → always 1 unit (strength is not stock qty)
      "2 tablets 500mg" → 2
    """
    if dosage is None:
        return 1
    s = str(dosage).strip().lower()
    if not s:
        return 1

    # Strength-only (mg/mcg/g/ml/iu) → 1 inventory unit per dose.
    # "500mg" has no word-boundary before mg — match digit + optional space + unit.
    has_strength = re.search(r"\d\s*(mg|mcg|µg|ug|g|ml|iu)\b", s) is not None
    has_count_unit = re.search(
        r"\b(tabs?|tablets?|caps?|capsules?|amps?|ampoules?|vials?|drops?|puffs?|sprays?|units?)\b",
        s,
    ) is not None

    if has_strength and not has_count_unit:
        return 1

    m = re.match(r"^\s*(\d+(?:\.\d+)?)", s)
    if not m:
        return 1
    try:
        n = float(m.group(1))
    except ValueError:
        return 1
    # Mis-parsed strength without unit label (e.g. bare "500")
    if n > 20 and not has_count_unit:
        return 1
    return max(1, int(round(n)))


DEFAULT_SCHEDULES = {
    1: ["08:00"],
    2: ["08:00", "20:00"],
    3: ["08:00", "14:00", "20:00"],
    4: ["08:00", "12:00", "16:00", "20:00"],
}


class NursingService:
    def __init__(
        self,
        assignment_repo,
        course_repo,
        item_repo,
        dose_repo,
        admission_repo=None,
        bed_repo=None,
        user_repo=None,
        medicine_repo=None,
        mar_repo=None,
        notification_service=None,
        pharmacy_service=None,
    ):
        self.assignment_repo = assignment_repo
        self.course_repo = course_repo
        self.item_repo = item_repo
        self.dose_repo = dose_repo
        self.admission_repo = admission_repo
        self.bed_repo = bed_repo
        self.user_repo = user_repo
        self.medicine_repo = medicine_repo
        self.mar_repo = mar_repo
        self.notification_service = notification_service
        self.pharmacy_service = pharmacy_service

    # ── Bed assignments ──────────────────────────────────────
    def assign_beds(self, db: Session, data: NurseBedAssignRequest, assigned_by: int | None):
        user = self.user_repo.get_by_id(db, data.nurse_user_id) if self.user_repo else None
        if not user:
            raise NotFoundException("Nurse user not found.")
        if user.role != "nurse" and user.role != "admin":
            raise BadRequestException("Selected user is not a nurse.")

        created = []
        with UnitOfWork(db):
            for bed_id in data.bed_ids:
                bed = self.bed_repo.get_by_id(db, bed_id) if self.bed_repo else None
                if not bed:
                    raise NotFoundException(f"Bed {bed_id} not found.")

                existing = (
                    db.query(NurseBedAssignment)
                    .filter(
                        NurseBedAssignment.nurse_user_id == data.nurse_user_id,
                        NurseBedAssignment.bed_id == bed_id,
                    )
                    .first()
                )
                if existing:
                    existing.is_active = True
                    existing.assigned_by = assigned_by
                    db.flush()
                    created.append(existing)
                else:
                    obj = NurseBedAssignment(
                        nurse_user_id=data.nurse_user_id,
                        bed_id=bed_id,
                        assigned_by=assigned_by,
                        is_active=True,
                    )
                    created.append(self.assignment_repo.create(db, obj))

        return ServiceResult.Success(
            "Beds assigned to nurse.",
            [self._enrich_assignment(db, a) for a in created],
        )

    def unassign_bed(self, db: Session, assignment_id: int):
        obj = self.assignment_repo.get_by_id(db, assignment_id)
        if not obj:
            raise NotFoundException("Assignment not found.")
        with UnitOfWork(db):
            obj.is_active = False
            db.flush()
        return ServiceResult.Success("Assignment removed.", None)

    def list_assignments(self, db: Session, nurse_user_id: int | None = None):
        if nurse_user_id:
            rows = self.assignment_repo.get_active_by_nurse(db, nurse_user_id)
        else:
            rows = self.assignment_repo.get_all_active(db)
        return ServiceResult.Success(
            "Assignments loaded.",
            [self._enrich_assignment(db, a) for a in rows],
        )

    def list_nurses(self, db: Session):
        if not self.user_repo:
            return ServiceResult.Success("OK", [])
        users = (
            db.query(self.user_repo.model)
            .filter(self.user_repo.model.role == "nurse")
            .all()
        )
        return ServiceResult.Success(
            "Nurses loaded.",
            [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role,
                }
                for u in users
            ],
        )

    def _enrich_assignment(self, db: Session, a: NurseBedAssignment) -> dict:
        bed = a.bed
        ward_name = bed.ward.name if bed and getattr(bed, "ward", None) else None
        bed_number = bed.bed_number if bed else None
        patient_name = None
        admission_id = None
        if bed and self.admission_repo:
            adm = (
                db.query(Admission)
                .filter(
                    Admission.bed_id == a.bed_id,
                    Admission.status == AdmissionStatus.ADMITTED.value,
                )
                .first()
            )
            if adm:
                admission_id = adm.id
                patient_name = adm.patient.name if adm.patient else None

        return {
            "id": a.id,
            "nurse_user_id": a.nurse_user_id,
            "bed_id": a.bed_id,
            "is_active": a.is_active,
            "assigned_at": a.assigned_at,
            "nurse_username": a.nurse.username if a.nurse else None,
            "ward_name": ward_name,
            "bed_number": bed_number,
            "patient_name": patient_name,
            "admission_id": admission_id,
        }

    # ── Medication courses ───────────────────────────────────

    def _create_pharmacy_orders_for_course(self, db: Session, admission, course, items_data, duration_days: int, course_items=None):
        """
        Hospital flow: ward course → pharmacy must dispense full course stock
        before nurses can mark doses as given.

        Quantity per line = times_per_day × duration_days (minimum 1).
        Form (tablet / injection / syrup / drip) is stored on the order for inventory clarity.
        """
        if not self.pharmacy_service:
            logger.warning("pharmacy_service not wired — course meds will not reach pharmacist")
            return

        from app.models.prescription import Prescription
        from app.models.prescription_item import PrescriptionItem
        from app.models.pharmacy_order import PharmacyOrder
        from app.common.enums import PharmacyOrderStatus

        ROUTE_TO_FORM = {
            "tablet": "tablet",
            "capsule": "capsule",
            "syrup": "syrup",
            "injection": "injection",
            "drip": "drip",
            "oral": "tablet",
            "iv": "drip",
            "im": "injection",
            "sc": "injection",
            "other": "other",
        }

        def times_for(freq, explicit=None):
            if explicit:
                return max(1, int(explicit))
            return FREQ_TIMES.get((freq or "OD").upper(), 1)

        prescription = Prescription(
            appointment_id=None,
            admission_id=admission.id,
            patient_id=admission.patient_id,
            doctor_id=course.ordered_by_doctor_id,
            diagnosis=None,
            advice=(course.title or "Ward Medication Course")
            + (f" — {course.clinical_notes}" if course.clinical_notes else "")
            + " [WARD COURSE — dispense full quantity before nursing]",
        )

        # Pair course DB items (with ids) to input data for quantity/form
        db_items = list(course_items or course.items or [])
        rx_items = []
        meta = []  # parallel: form, qty, course_item_id, medicine_name

        for idx, item_data in enumerate(items_data):
            medicine_name = getattr(item_data, "medicine_name", None)
            dosage = getattr(item_data, "dosage", None)
            frequency = getattr(item_data, "frequency", None) or "OD"
            instructions = getattr(item_data, "instructions", None)
            route = (getattr(item_data, "route", None) or "tablet").lower()
            drip = getattr(item_data, "drip_rate", None)
            tpd = times_for(frequency, getattr(item_data, "times_per_day", None))
            if not medicine_name or not dosage:
                continue

            # Skip if already pending/dispensed for same patient+name
            exists = (
                db.query(PharmacyOrder)
                .filter(
                    PharmacyOrder.patient_id == admission.patient_id,
                    PharmacyOrder.status.in_(
                        [PharmacyOrderStatus.PENDING.value, PharmacyOrderStatus.DISPENSED.value]
                    ),
                )
                .all()
            )
            # check by joining prescription item names is heavy; use course_item link later
            form = ROUTE_TO_FORM.get(route, "other")
            units_per_dose = units_from_dosage(dosage)
            days = max(1, int(duration_days or 1))
            # Stock units = (tablets per dose) × (times per day) × (days)
            # e.g. 1 tab OD × 3 days = 3 — NEVER multiply mg strength into stock
            qty = max(1, int(units_per_dose) * int(tpd) * days)
            extra = [
                f"Form: {form}",
                f"Course qty: {qty} (= {units_per_dose} × {tpd}/day × {days} day(s))",
                f"Dosage: {dosage}",
            ]
            if route:
                extra.append(f"Route: {route}")
            if drip:
                extra.append(f"Drip rate: {drip}")
            if instructions:
                extra.append(instructions)

            ci = db_items[idx] if idx < len(db_items) else None
            # prefer matching by name if order differs
            if ci is None or (ci.medicine_name or "").lower() != medicine_name.lower():
                for c in db_items:
                    if (c.medicine_name or "").lower() == medicine_name.lower():
                        ci = c
                        break

            rx_items.append(
                PrescriptionItem(
                    medicine_name=medicine_name,
                    dosage=dosage,
                    frequency=frequency,
                    duration=f"{duration_days} day(s)",
                    instructions=" · ".join(extra),
                    quantity=qty,
                )
            )
            meta.append({
                "form": form,
                "qty": qty,
                "course_item_id": ci.id if ci else None,
                "medicine_name": medicine_name,
            })

        if not rx_items:
            return

        prescription.items = rx_items
        db.add(prescription)
        db.flush()

        # Create orders with quantity + form + course link
        from app.models.pharmacy_order import PharmacyOrder as PO
        for item, m in zip(prescription.items, meta):
            # dedupe by name on pending
            from app.models.prescription_item import PrescriptionItem as PI
            dup = (
                db.query(PO)
                .join(PI, PI.id == PO.prescription_item_id)
                .filter(
                    PO.patient_id == admission.patient_id,
                    PI.medicine_name.ilike(m["medicine_name"].strip()),
                    PO.status == PharmacyOrderStatus.PENDING.value,
                )
                .first()
            )
            if dup:
                logger.info(f"Reuse pending pharmacy order #{dup.id} for {m['medicine_name']}")
                if m["course_item_id"]:
                    from app.models.medication_course import MedicationCourseItem
                    ci = db.query(MedicationCourseItem).filter(
                        MedicationCourseItem.id == m["course_item_id"]
                    ).first()
                    if ci:
                        ci.pharmacy_order_id = dup.id
                        dup.course_item_id = ci.id
                        dup.source = "course"
                        if not dup.form:
                            dup.form = m["form"]
                continue

            medicine = None
            if self.medicine_repo:
                medicine = self.medicine_repo.get_by_name(db, item.medicine_name)
                # Prefer inventory row matching form when possible
                if medicine and m["form"] and getattr(medicine, "form", None):
                    if str(medicine.form).lower() != m["form"] and self.medicine_repo:
                        # try find same name is unique so keep it; pharmacist sees form on order
                        pass

            order = PO(
                prescription_item_id=item.id,
                patient_id=admission.patient_id,
                medicine_id=medicine.id if medicine else None,
                status=PharmacyOrderStatus.PENDING.value,
                quantity=m["qty"],
                source="course",
                course_item_id=m["course_item_id"],
                form=m["form"],
            )
            db.add(order)
            db.flush()
            if m["course_item_id"]:
                from app.models.medication_course import MedicationCourseItem
                ci = db.query(MedicationCourseItem).filter(
                    MedicationCourseItem.id == m["course_item_id"]
                ).first()
                if ci:
                    ci.pharmacy_order_id = order.id

        # Notify pharmacist
        try:
            self.pharmacy_service._notify_role(
                db,
                role="pharmacist",
                title="Ward course — dispense required",
                body=f"Admission #{admission.id}: {len(meta)} medicine line(s) awaiting dispense before nursing can give doses.",
            )
        except Exception as e:
            logger.warning(f"Pharmacist notify failed: {e}")


    def create_course(self, db: Session, data: MedicationCourseCreate):
        admission = self.admission_repo.get_by_id(db, data.admission_id)
        if not admission:
            raise NotFoundException("Admission not found.")

        if admission.status not in (
            AdmissionStatus.ADMITTED.value,
            AdmissionStatus.PENDING.value,
        ):
            raise BadRequestException(
                "Can only create courses for pending or admitted patients."
            )

        end_date = data.start_date + timedelta(days=max(data.duration_days - 1, 0))

        with UnitOfWork(db):
            course = MedicationCourse(
                admission_id=data.admission_id,
                ordered_by_doctor_id=data.ordered_by_doctor_id,
                title=data.title or "Ward Medication Course",
                status="active",
                start_date=data.start_date,
                end_date=end_date,
                duration_days=data.duration_days,
                clinical_notes=data.clinical_notes,
            )
            course = self.course_repo.create(db, course)

            for idx, item_data in enumerate(data.items):
                times_per_day = item_data.times_per_day
                if not times_per_day:
                    times_per_day = FREQ_TIMES.get(
                        (item_data.frequency or "OD").upper(), 1
                    )
                schedule = item_data.schedule_times
                if not schedule:
                    schedule = ",".join(
                        DEFAULT_SCHEDULES.get(times_per_day, DEFAULT_SCHEDULES[1])
                    )

                med_id = item_data.medicine_id
                if not med_id and self.medicine_repo and item_data.medicine_name:
                    match = self.medicine_repo.get_by_name(db, item_data.medicine_name)
                    if match:
                        med_id = match.id
                item = MedicationCourseItem(
                    course_id=course.id,
                    medicine_id=med_id,
                    medicine_name=item_data.medicine_name,
                    route=(item_data.route or "tablet").lower(),
                    dosage=item_data.dosage,
                    frequency=item_data.frequency or "OD",
                    times_per_day=times_per_day,
                    schedule_times=schedule,
                    drip_rate=item_data.drip_rate,
                    instructions=item_data.instructions,
                    sort_order=item_data.sort_order if item_data.sort_order is not None else idx,
                )
                item = self.item_repo.create(db, item)
                self._generate_doses(db, course, item)

            # Pharmacy first: full course quantity must be dispensed before nurses give doses
            db_items = list(course.items) if course.items is not None else []
            # reload items from session
            course = self.course_repo.get_by_id_full(db, course.id) or course
            self._create_pharmacy_orders_for_course(
                db, admission, course, data.items, data.duration_days,
                course_items=list(course.items or []),
            )

            course = self.course_repo.get_by_id_full(db, course.id)

        self._notify_nurses_for_admission(
            db,
            admission,
            title="New medication course",
            body=f"Doctor ordered a medication course for admission #{admission.id}.",
        )

        return ServiceResult.Success("Medication course created.", self._enrich_course(db, course))

    def update_course(self, db: Session, course_id: int, data: MedicationCourseUpdate):
        course = self.course_repo.get_by_id_full(db, course_id)
        if not course:
            raise NotFoundException("Course not found.")

        admission = self.admission_repo.get_by_id(db, course.admission_id) if self.admission_repo else None

        with UnitOfWork(db):
            if data.title is not None:
                course.title = data.title
            if data.status is not None:
                course.status = data.status
            if data.clinical_notes is not None:
                course.clinical_notes = data.clinical_notes
            if data.duration_days is not None and data.duration_days != course.duration_days:
                course.duration_days = data.duration_days
                course.end_date = course.start_date + timedelta(days=max(data.duration_days - 1, 0))
                # Regenerate future pending doses only if items replaced
            if data.items is not None:
                # Remove future pending doses and items, rebuild
                for dose in list(course.doses or []):
                    if dose.status == "pending" and dose.scheduled_date >= date.today():
                        db.delete(dose)
                for item in list(course.items or []):
                    db.delete(item)
                db.flush()
                for idx, item_data in enumerate(data.items):
                    times_per_day = item_data.times_per_day or FREQ_TIMES.get(
                        (item_data.frequency or "OD").upper(), 1
                    )
                    schedule = item_data.schedule_times or ",".join(
                        DEFAULT_SCHEDULES.get(times_per_day, DEFAULT_SCHEDULES[1])
                    )
                    item = MedicationCourseItem(
                        course_id=course.id,
                        medicine_id=item_data.medicine_id,
                        medicine_name=item_data.medicine_name,
                        route=(item_data.route or "tablet").lower(),
                        dosage=item_data.dosage,
                        frequency=item_data.frequency or "OD",
                        times_per_day=times_per_day,
                        schedule_times=schedule,
                        drip_rate=item_data.drip_rate,
                        instructions=item_data.instructions,
                        sort_order=idx,
                    )
                    item = self.item_repo.create(db, item)
                    self._generate_doses(db, course, item)

                # Re-issue pharmacy orders for the new course items
                if admission is None:
                    admission = self.admission_repo.get_by_id(db, course.admission_id)
                if admission:
                    self._create_pharmacy_orders_for_course(
                        db, admission, course, data.items, course.duration_days
                    )

            db.flush()
            course = self.course_repo.get_by_id_full(db, course_id)

        return ServiceResult.Success("Course updated.", self._enrich_course(db, course))

    def get_course(self, db: Session, course_id: int):
        course = self.course_repo.get_by_id_full(db, course_id)
        if not course:
            raise NotFoundException("Course not found.")
        return ServiceResult.Success("OK", self._enrich_course(db, course))

    def list_courses_for_admission(self, db: Session, admission_id: int):
        rows = self.course_repo.get_by_admission(db, admission_id)
        return ServiceResult.Success(
            "OK",
            [self._enrich_course(db, c) for c in rows],
        )

    def _generate_doses(self, db: Session, course: MedicationCourse, item: MedicationCourseItem):
        times = [t.strip() for t in (item.schedule_times or "08:00").split(",") if t.strip()]
        if not times:
            times = DEFAULT_SCHEDULES.get(item.times_per_day, ["08:00"])

        for day_offset in range(course.duration_days):
            day = course.start_date + timedelta(days=day_offset)
            for t in times:
                dose = MedicationCourseDose(
                    course_id=course.id,
                    course_item_id=item.id,
                    admission_id=course.admission_id,
                    scheduled_date=day,
                    scheduled_time=t,
                    status="pending",
                )
                self.dose_repo.create(db, dose)

    def _enrich_course(self, db: Session, course: MedicationCourse) -> dict:
        admission = course.admission
        patient_name = None
        bed_label = None
        if admission:
            patient_name = admission.patient.name if admission.patient else None
            if admission.bed:
                ward = admission.bed.ward.name if admission.bed.ward else "Ward"
                bed_label = f"{ward} — Bed {admission.bed.bed_number}"

        today = date.today()
        pending = given = 0
        for d in course.doses or []:
            if d.scheduled_date == today:
                if d.status == "pending":
                    pending += 1
                elif d.status == "given":
                    given += 1

        return {
            "id": course.id,
            "admission_id": course.admission_id,
            "ordered_by_doctor_id": course.ordered_by_doctor_id,
            "title": course.title,
            "status": course.status,
            "start_date": course.start_date,
            "end_date": course.end_date,
            "duration_days": course.duration_days,
            "clinical_notes": course.clinical_notes,
            "created_at": course.created_at,
            "doctor_name": (
                course.ordered_by_doctor.full_name
                if course.ordered_by_doctor
                else None
            ),
            "patient_name": patient_name,
            "bed_label": bed_label,
            "items": [
                {
                    "id": i.id,
                    "medicine_id": i.medicine_id,
                    "medicine_name": i.medicine_name,
                    "route": i.route,
                    "dosage": i.dosage,
                    "frequency": i.frequency,
                    "times_per_day": i.times_per_day,
                    "schedule_times": i.schedule_times,
                    "drip_rate": i.drip_rate,
                    "instructions": i.instructions,
                    "sort_order": i.sort_order,
                }
                for i in sorted(course.items or [], key=lambda x: x.sort_order)
            ],
            "today_pending": pending,
            "today_given": given,
        }

    # ── Dose actions (nurse) ─────────────────────────────────
    def get_today_doses_for_nurse(self, db: Session, nurse_user_id: int, day: date | None = None):
        day = day or date.today()
        if not nurse_user_id:
            return ServiceResult.Success("Nurse user not resolved — please log out and log in again.", [])
        assignments = self.assignment_repo.get_active_by_nurse(db, nurse_user_id)
        bed_ids = [a.bed_id for a in assignments]
        if not bed_ids:
            return ServiceResult.Success("No beds assigned.", [])

        doses = self.dose_repo.get_for_date_beds(db, bed_ids, day)
        return ServiceResult.Success(
            "OK",
            [self._enrich_dose(d) for d in doses],
        )

    def get_doses_for_admission(
        self, db: Session, admission_id: int, day: date | None = None
    ):
        day = day or date.today()
        doses = self.dose_repo.get_for_date_admission(db, admission_id, day)
        return ServiceResult.Success("OK", [self._enrich_dose(d) for d in doses])

    def act_on_dose(
        self,
        db: Session,
        dose_id: int,
        data: DoseActionRequest,
        nurse_user_id: int | None,
    ):
        dose = self.dose_repo.get_by_id(db, dose_id)
        if not dose:
            raise NotFoundException("Dose not found.")
        if dose.status == "given":
            raise ConflictException("Dose already marked as given.")

        status = (data.status or "").lower().strip()
        if status not in ("given", "held", "missed", "skipped"):
            raise BadRequestException("Status must be given, held, missed, or skipped.")

        # Hospital rule: nurse can mark GIVEN only after pharmacy dispensed the course medicine
        if status == "given":
            from app.models.pharmacy_order import PharmacyOrder
            from app.models.prescription_item import PrescriptionItem
            from app.common.enums import PharmacyOrderStatus

            item = dose.item
            order = None
            if item is not None and getattr(item, "pharmacy_order_id", None):
                order = db.query(PharmacyOrder).filter(
                    PharmacyOrder.id == item.pharmacy_order_id
                ).first()
            if order is not None:
                if order.status != PharmacyOrderStatus.DISPENSED.value:
                    raise BadRequestException(
                        "Pharmacy has not dispensed this medicine yet. "
                        "Ward stock must be dispensed before the nurse can mark the dose as given."
                    )
            elif item is not None and item.medicine_name:
                adm = (
                    self.admission_repo.get_by_id(db, dose.admission_id)
                    if self.admission_repo
                    else None
                )
                patient_id = adm.patient_id if adm else None
                dispensed = None
                if patient_id:
                    dispensed = (
                        db.query(PharmacyOrder)
                        .join(
                            PrescriptionItem,
                            PrescriptionItem.id == PharmacyOrder.prescription_item_id,
                        )
                        .filter(
                            PharmacyOrder.patient_id == patient_id,
                            PrescriptionItem.medicine_name.ilike(item.medicine_name.strip()),
                            PharmacyOrder.status == PharmacyOrderStatus.DISPENSED.value,
                        )
                        .first()
                    )
                if not dispensed:
                    raise BadRequestException(
                        f"'{item.medicine_name}' has not been dispensed by pharmacy. "
                        "Dispense the ward course in the pharmacy portal first, then mark given."
                    )

        # Resolve admission (optional safety check — do not block status update if repo missing)
        if self.admission_repo:
            admission = self.admission_repo.get_by_id(db, dose.admission_id)
            if not admission:
                raise NotFoundException("Admission not found.")

        medicine_name = dose.item.medicine_name if dose.item else "medicine"
        medicine_id = dose.item.medicine_id if dose.item else None
        admission_id = dose.admission_id

        mar = None
        with UnitOfWork(db):
            dose.status = status
            dose.notes = data.notes
            dose.given_by = nurse_user_id
            dose.given_at = datetime.now(timezone.utc)

            if status == "given" and medicine_id and self.mar_repo:
                mar = MedicationAdministration(
                    admission_id=admission_id,
                    medicine_id=medicine_id,
                    scheduled_time=None,
                    given_by=nurse_user_id,
                )
                mar = self.mar_repo.create(db, mar)
                dose.medication_administration_id = mar.id

                # Decrement stock if pharmacy medicine linked
                if self.medicine_repo:
                    med = self.medicine_repo.get_by_id(db, medicine_id)
                    if med and getattr(med, "stock_qty", None) is not None and med.stock_qty > 0:
                        med.stock_qty = max(0, med.stock_qty - 1)
                        db.flush()

            db.flush()

        # Re-load after commit so response enrichment does not hit expired/detached state
        dose = self.dose_repo.get_by_id(db, dose_id) or dose

        # Notify admission head so MAR / compliance stays in sync in their portal
        self._notify_role(
            db,
            "admission_head",
            f"MAR update — dose {status}",
            f"Admission #{admission_id}: {medicine_name} marked {status}.",
        )

        return ServiceResult.Success("Dose updated.", self._enrich_dose(dose))

    def _enrich_dose(self, dose: MedicationCourseDose) -> dict:
        item = dose.item
        admission = dose.admission
        bed_label = None
        patient_name = None
        if admission:
            patient_name = admission.patient.name if admission.patient else None
            if admission.bed:
                ward = admission.bed.ward.name if admission.bed.ward else "Ward"
                bed_label = f"{ward} — Bed {admission.bed.bed_number}"

        pharmacy_status = None
        pharmacy_ready = True
        if item is not None and getattr(item, "pharmacy_order_id", None):
            from app.models.pharmacy_order import PharmacyOrder
            from app.common.enums import PharmacyOrderStatus
            po = (
                # use object session if available
                item.pharmacy_order
                if getattr(item, "pharmacy_order", None) is not None
                else None
            )
            if po is None:
                try:
                    from sqlalchemy.orm import object_session
                    sess = object_session(dose)
                    if sess is not None:
                        po = sess.query(PharmacyOrder).filter(
                            PharmacyOrder.id == item.pharmacy_order_id
                        ).first()
                except Exception:
                    po = None
            if po is not None:
                pharmacy_status = po.status
                pharmacy_ready = po.status == PharmacyOrderStatus.DISPENSED.value
            else:
                pharmacy_status = "pending"
                pharmacy_ready = False
        elif item is not None:
            # no linked order — still show not ready until fallback dispensed exists
            pharmacy_status = "unknown"
            pharmacy_ready = False

        return {
            "id": dose.id,
            "course_id": dose.course_id,
            "course_item_id": dose.course_item_id,
            "admission_id": dose.admission_id,
            "scheduled_date": dose.scheduled_date,
            "scheduled_time": dose.scheduled_time,
            "status": dose.status,
            "given_by": dose.given_by,
            "given_at": dose.given_at,
            "notes": dose.notes,
            "medicine_name": item.medicine_name if item else None,
            "dosage": item.dosage if item else None,
            "route": item.route if item else None,
            "drip_rate": item.drip_rate if item else None,
            "instructions": item.instructions if item else None,
            "patient_name": patient_name,
            "bed_label": bed_label,
            "pharmacy_status": pharmacy_status,
            "pharmacy_ready": pharmacy_ready,
            "form": (item.route if item else None),
        }

    def nurse_dashboard(self, db: Session, nurse_user_id: int):
        today = date.today()
        if not nurse_user_id:
            return ServiceResult.Success(
                "OK",
                {
                    "assigned_beds": 0,
                    "active_patients": 0,
                    "doses_pending_today": 0,
                    "doses_given_today": 0,
                    "doses_held_today": 0,
                },
            )
        assignments = self.assignment_repo.get_active_by_nurse(db, nurse_user_id)
        bed_ids = [a.bed_id for a in assignments]
        active_patients = 0
        if bed_ids:
            active_patients = (
                db.query(Admission)
                .filter(
                    Admission.bed_id.in_(bed_ids),
                    Admission.status == AdmissionStatus.ADMITTED.value,
                )
                .count()
            )

        pending = given = held = 0
        if bed_ids:
            pending = self.dose_repo.count_by_status_date_beds(db, bed_ids, today, "pending")
            given = self.dose_repo.count_by_status_date_beds(db, bed_ids, today, "given")
            held = self.dose_repo.count_by_status_date_beds(db, bed_ids, today, "held")

        return ServiceResult.Success(
            "OK",
            {
                "assigned_beds": len(bed_ids),
                "active_patients": active_patients,
                "doses_pending_today": pending,
                "doses_given_today": given,
                "doses_held_today": held,
            },
        )

    def admission_med_compliance(self, db: Session, admission_id: int, day: date | None = None):
        """For admission head portal — today's dose progress on an admission."""
        day = day or date.today()
        doses = self.dose_repo.get_for_date_admission(db, admission_id, day)
        total = len(doses)
        given = sum(1 for d in doses if d.status == "given")
        pending = sum(1 for d in doses if d.status == "pending")
        held = sum(1 for d in doses if d.status == "held")
        missed = sum(1 for d in doses if d.status == "missed")
        return ServiceResult.Success(
            "OK",
            {
                "admission_id": admission_id,
                "date": day.isoformat(),
                "total": total,
                "given": given,
                "pending": pending,
                "held": held,
                "missed": missed,
                "doses": [self._enrich_dose(d) for d in doses],
            },
        )

    def _notify_nurses_for_admission(self, db: Session, admission: Admission, title: str, body: str):
        if not admission.bed_id:
            return
        assignments = self.assignment_repo.get_active_by_bed(db, admission.bed_id)
        for a in assignments:
            try:
                from app.services.firebase_service import send_notification
                user = a.nurse
                token = getattr(user, "fcm_token", None) if user else None
                if token:
                    send_notification(token, title=title, body=body)
            except Exception as e:
                logger.warning(f"Nurse notify failed: {e}")

    def _notify_role(self, db: Session, role: str, title: str, body: str):
        if not self.user_repo:
            return
        try:
            users = db.query(self.user_repo.model).filter(self.user_repo.model.role == role).all()
            from app.services.firebase_service import send_notification
            for u in users:
                token = getattr(u, "fcm_token", None)
                if token:
                    send_notification(token, title=title, body=body)
        except Exception as e:
            logger.warning(f"Role notify ({role}) failed: {e}")
