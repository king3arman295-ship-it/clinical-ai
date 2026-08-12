from datetime import datetime

from sqlalchemy.orm import Session

from app.common.enums import (
    AdmissionStatus,
    BedStatus,
    PatientCareType,
)
from app.common.messages import Messages
from app.common.service_result import ServiceResult

from app.core.logger import logger
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    BadRequestException,
    ConflictException,
)

from app.models.admission import Admission
from app.models.admission_note import AdmissionNote

from app.schemas.admission import (
    AdmissionRequestCreate,
    BedAllocationRequest,
    DischargeRequest,
    AdmissionNoteCreate,
    AdmissionConditionUpdate,
    WardCreate,
    WardUpdate,
    BedCreate,
    BedUpdate,
    BedMapEntry,
    PatientAdmissionView,
)


class AdmissionService:

    def __init__(
        self,
        patient_repository,
        doctor_repository,
        ward_repository,
        bed_repository,
        admission_repository,
        admission_note_repository,
        user_repository=None,
    ):
        self.patient_repo = patient_repository
        self.doctor_repo = doctor_repository
        self.ward_repo = ward_repository
        self.bed_repo = bed_repository
        self.admission_repo = admission_repository
        self.note_repo = admission_note_repository
        self.user_repo = user_repository

    # ═════════════════════════════════════════════════════
    # Wards
    # ═════════════════════════════════════════════════════
    def create_ward(self, db: Session, data: WardCreate) -> ServiceResult:
        from app.models.ward import Ward

        ward = Ward(
            name=data.name,
            type=data.type.value,
            total_beds=data.total_beds,
            daily_rate=float(getattr(data, "daily_rate", None) or 2000.0),
        )

        with UnitOfWork(db):
            created = self.ward_repo.create(db, ward)

        return ServiceResult.Success(Messages.WARD_CREATED, created)

    def get_wards(self, db: Session) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS,
            self.ward_repo.get_all(db),
        )

    def update_ward(
        self, db: Session, ward_id: int, data: WardUpdate
    ) -> ServiceResult:
        ward = self.ward_repo.get_by_id(db, ward_id)
        if not ward:
            raise NotFoundException(Messages.WARD_NOT_FOUND)

        if data.name is not None:
            ward.name = data.name
        if data.type is not None:
            ward.type = data.type.value
        if data.total_beds is not None:
            ward.total_beds = data.total_beds
        if getattr(data, "daily_rate", None) is not None:
            ward.daily_rate = float(data.daily_rate)

        with UnitOfWork(db):
            updated = self.ward_repo.update(db, ward)

        return ServiceResult.Success(Messages.WARD_UPDATED, updated)

    # ═════════════════════════════════════════════════════
    # Beds
    # ═════════════════════════════════════════════════════
    def create_bed(self, db: Session, data: BedCreate) -> ServiceResult:
        from app.models.bed import Bed

        ward = self.ward_repo.get_by_id(db, data.ward_id)
        if not ward:
            raise NotFoundException(Messages.WARD_NOT_FOUND)

        bed = Bed(
            ward_id=data.ward_id,
            bed_number=data.bed_number,
            status=data.status.value,
        )

        with UnitOfWork(db):
            created = self.bed_repo.create(db, bed)
            ward.total_beds = (ward.total_beds or 0) + 1
            self.ward_repo.update(db, ward)

        return ServiceResult.Success(Messages.BED_CREATED, created)

    def get_beds(self, db: Session, ward_id: int | None = None) -> ServiceResult:
        beds = (
            self.bed_repo.get_by_ward(db, ward_id)
            if ward_id
            else self.bed_repo.get_all(db)
        )
        for bed in beds:
            try:
                bed.ward_name = bed.ward.name if getattr(bed, "ward", None) else None
            except Exception:
                bed.ward_name = None
        return ServiceResult.Success(Messages.SUCCESS, beds)

    def update_bed(
        self, db: Session, bed_id: int, data: BedUpdate
    ) -> ServiceResult:
        bed = self.bed_repo.get_by_id(db, bed_id)
        if not bed:
            raise NotFoundException(Messages.BED_NOT_FOUND)

        if data.bed_number is not None:
            bed.bed_number = data.bed_number
        if data.status is not None:
            bed.status = data.status.value

        with UnitOfWork(db):
            updated = self.bed_repo.update(db, bed)

        return ServiceResult.Success(Messages.BED_UPDATED, updated)

    def get_bed_map(self, db: Session) -> ServiceResult:
        """
        Live bed-map for the Admission Head's dashboard: every bed, its
        ward, and — if occupied — who's in it, since when, under which
        doctor, and their condition flag.
        """
        beds = self.bed_repo.get_all(db)
        active_admissions = {
            a.bed_id: a for a in self.admission_repo.get_active(db)
        }

        entries = []
        for bed in beds:
            admission = active_admissions.get(bed.id)
            entries.append(
                BedMapEntry(
                    bed_id=bed.id,
                    ward_id=bed.ward_id,
                    ward_name=bed.ward.name if bed.ward else "",
                    ward_type=bed.ward.type if bed.ward else "general",
                    bed_number=bed.bed_number,
                    status=bed.status,
                    admission_id=admission.id if admission else None,
                    patient_id=admission.patient_id if admission else None,
                    patient_name=(
                        admission.patient.name
                        if admission and admission.patient
                        else None
                    ),
                    admitted_since=admission.admitted_at if admission else None,
                    admitting_doctor_id=(
                        admission.admitting_doctor_id if admission else None
                    ),
                    admitting_doctor_name=(
                        admission.admitting_doctor.full_name
                        if admission
                        and admission.admitting_doctor
                        else None
                    ),
                    condition_flag=(
                        admission.condition_flag if admission else None
                    ),
                )
            )

        return ServiceResult.Success(Messages.SUCCESS, entries)

    # ═════════════════════════════════════════════════════
    # Admission Requests (raised by a doctor)
    # ═════════════════════════════════════════════════════
    def create_admission_request(
        self,
        db: Session,
        requesting_doctor_id: int,
        data: AdmissionRequestCreate,
    ) -> ServiceResult:

        patient = self.patient_repo.get_by_id(db, data.patient_id)
        if not patient:
            raise NotFoundException(Messages.PATIENT_NOT_FOUND)

        doctor = self.doctor_repo.get_by_id(db, requesting_doctor_id)
        if not doctor:
            raise NotFoundException(Messages.DOCTOR_NOT_FOUND)

        existing = self.admission_repo.get_current_admission_for_patient(
            db, data.patient_id
        )
        if existing:
            raise ConflictException(Messages.ADMISSION_ALREADY_ADMITTED)

        admission = Admission(
            patient_id=data.patient_id,
            requesting_doctor_id=requesting_doctor_id,
            reason=data.reason,
            diagnosis=data.diagnosis,
            urgency=data.urgency.value,
            preferred_ward_type=(
                data.preferred_ward_type.value
                if data.preferred_ward_type
                else None
            ),
            status=AdmissionStatus.PENDING.value,
        )

        with UnitOfWork(db):
            created = self.admission_repo.create(db, admission)

        logger.info(
            f"Admission request created | ID={created.id} | "
            f"Patient={data.patient_id} | Doctor={requesting_doctor_id} | "
            f"Urgency={data.urgency.value}"
        )

        self._notify_role(
            db,
            role="admission_head",
            title="New Admission Request",
            body=(
                f"{patient.name} needs a "
                f"{data.preferred_ward_type.value if data.preferred_ward_type else 'general'} "
                f"bed ({data.urgency.value})."
            ),
        )

        return ServiceResult.Success(
            Messages.ADMISSION_REQUEST_CREATED, created
        )

    def get_pending_admissions(self, db: Session) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS,
            self.admission_repo.get_pending(db),
        )

    def get_bed_map_admissions(self, db: Session) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS,
            self.admission_repo.get_active(db),
        )

    def get_admission_by_id(self, db: Session, admission_id: int) -> ServiceResult:
        admission = self.admission_repo.get_by_id(db, admission_id)
        if not admission:
            raise NotFoundException(Messages.ADMISSION_NOT_FOUND)
        return ServiceResult.Success(Messages.SUCCESS, admission)

    def get_admissions_for_patient(
        self, db: Session, patient_id: int
    ) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS,
            self.admission_repo.get_by_patient(db, patient_id),
        )

    def get_my_admissions(self, db: Session, patient_id: int) -> ServiceResult:
        """Patient-facing version — plain ward/bed/doctor labels, no
        internal IDs or clinical rounds notes."""
        admissions = self.admission_repo.get_by_patient(db, patient_id)

        views = [
            PatientAdmissionView(
                id=a.id,
                status=a.status,
                urgency=a.urgency,
                reason=a.reason,
                diagnosis=a.diagnosis,
                ward_name=(a.bed.ward.name if a.bed and a.bed.ward else None),
                bed_number=(a.bed.bed_number if a.bed else None),
                admitting_doctor_name=(
                    a.admitting_doctor.full_name if a.admitting_doctor else None
                ),
                condition_flag=a.condition_flag,
                discharge_summary=a.discharge_summary,
                requested_at=a.requested_at,
                admitted_at=a.admitted_at,
                discharged_at=a.discharged_at,
            )
            for a in admissions
        ]

        return ServiceResult.Success(Messages.SUCCESS, views)

    def get_admissions_for_doctor(
        self, db: Session, doctor_id: int
    ) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS,
            self.admission_repo.get_by_doctor(db, doctor_id),
        )

    # ═════════════════════════════════════════════════════
    # Bed Allocation (Admission Head fulfils the request)
    # ═════════════════════════════════════════════════════
    def allocate_bed(
        self,
        db: Session,
        admission_id: int,
        data: BedAllocationRequest,
    ) -> ServiceResult:

        admission = self.admission_repo.get_by_id(db, admission_id)
        if not admission:
            raise NotFoundException(Messages.ADMISSION_NOT_FOUND)

        if admission.status != AdmissionStatus.PENDING.value:
            raise BadRequestException(Messages.ADMISSION_NOT_PENDING)

        bed = self.bed_repo.get_by_id(db, data.bed_id)
        if not bed:
            raise NotFoundException(Messages.BED_NOT_FOUND)

        if bed.status != BedStatus.VACANT.value:
            raise BadRequestException(Messages.BED_NOT_VACANT)

        patient = self.patient_repo.get_by_id(db, admission.patient_id)

        with UnitOfWork(db):
            bed.status = BedStatus.OCCUPIED.value
            self.bed_repo.update(db, bed)

            admission.bed_id = bed.id
            admission.admitting_doctor_id = (
                data.admitting_doctor_id or admission.requesting_doctor_id
            )
            admission.status = AdmissionStatus.ADMITTED.value
            admission.admitted_at = datetime.utcnow()
            updated = self.admission_repo.update(db, admission)

            if patient:
                patient.care_type = PatientCareType.IPD.value
                self.patient_repo.update(db, patient)

        logger.info(
            f"Bed allocated | Admission={admission_id} | Bed={bed.id} | "
            f"Patient={admission.patient_id}"
        )

        return ServiceResult.Success(Messages.ADMISSION_ALLOCATED, updated)

    # ═════════════════════════════════════════════════════
    # Discharge
    # ═════════════════════════════════════════════════════
    def discharge_patient(
        self,
        db: Session,
        admission_id: int,
        data: DischargeRequest,
    ) -> ServiceResult:

        admission = self.admission_repo.get_by_id(db, admission_id)
        if not admission:
            raise NotFoundException(Messages.ADMISSION_NOT_FOUND)

        if admission.status != AdmissionStatus.ADMITTED.value:
            raise BadRequestException(Messages.ADMISSION_NOT_ADMITTED)

        bed = self.bed_repo.get_by_id(db, admission.bed_id) if admission.bed_id else None
        patient = self.patient_repo.get_by_id(db, admission.patient_id)

        with UnitOfWork(db):
            if bed:
                bed.status = BedStatus.VACANT.value
                self.bed_repo.update(db, bed)

            admission.status = AdmissionStatus.DISCHARGED.value
            admission.discharge_summary = data.discharge_summary
            admission.discharged_at = datetime.utcnow()
            updated = self.admission_repo.update(db, admission)

            if patient:
                patient.care_type = PatientCareType.OPD.value
                self.patient_repo.update(db, patient)

        logger.info(
            f"Patient discharged | Admission={admission_id} | "
            f"Bed freed={admission.bed_id}"
        )

        return ServiceResult.Success(Messages.ADMISSION_DISCHARGED, updated)

    # ═════════════════════════════════════════════════════
    # Rounds / Progress Notes
    # ═════════════════════════════════════════════════════
    def add_admission_note(
        self,
        db: Session,
        admission_id: int,
        doctor_id: int,
        data: AdmissionNoteCreate,
    ) -> ServiceResult:

        admission = self.admission_repo.get_by_id(db, admission_id)
        if not admission:
            raise NotFoundException(Messages.ADMISSION_NOT_FOUND)

        note = AdmissionNote(
            admission_id=admission_id,
            doctor_id=doctor_id,
            note=data.note,
            vitals=data.vitals,
        )

        with UnitOfWork(db):
            created = self.note_repo.create(db, note)

        return ServiceResult.Success(Messages.ADMISSION_NOTE_ADDED, created)

    def get_admission_notes(
        self, db: Session, admission_id: int
    ) -> ServiceResult:
        return ServiceResult.Success(
            Messages.SUCCESS,
            self.note_repo.get_by_admission(db, admission_id),
        )

    def update_condition(
        self,
        db: Session,
        admission_id: int,
        data: AdmissionConditionUpdate,
    ) -> ServiceResult:
        admission = self.admission_repo.get_by_id(db, admission_id)
        if not admission:
            raise NotFoundException(Messages.ADMISSION_NOT_FOUND)

        with UnitOfWork(db):
            admission.condition_flag = data.condition_flag.value
            updated = self.admission_repo.update(db, admission)

        return ServiceResult.Success(Messages.SUCCESS, updated)

    # ═════════════════════════════════════════════════════
    # Notifications
    # ═════════════════════════════════════════════════════

    def cancel_admission_request(
        self,
        db: Session,
        admission_id: int,
        reason: str | None = None,
    ) -> ServiceResult:
        """Admission manager cancels a pending request so the doctor can re-request."""
        admission = self.admission_repo.get_by_id(db, admission_id)
        if not admission:
            raise NotFoundException(Messages.ADMISSION_NOT_FOUND)

        status = str(getattr(admission.status, "value", admission.status) or "").lower()
        if status != AdmissionStatus.PENDING.value:
            raise ConflictException(
                f"Only pending admission requests can be cancelled (current: {status})."
            )

        with UnitOfWork(db):
            admission.status = AdmissionStatus.CANCELLED.value
            updated = self.admission_repo.update(db, admission)

        reason_txt = f" Reason: {reason}." if reason else ""
        body = (
            f"Admission request #{admission_id} was cancelled by admission desk."
            f"{reason_txt} You may submit a new admission request if still needed."
        )
        self._notify_role(db, role="doctor", title="Admission request cancelled", body=body)
        # patient + requesting doctor FCM
        try:
            from app.services.firebase_service import send_notification
            from app.models.patient import Patient
            patient = self.patient_repo.get_by_id(db, admission.patient_id)
            if patient and getattr(patient, "fcm_token", None):
                send_notification(token=patient.fcm_token, title="Admission request cancelled", body=body)
            doctor = self.doctor_repo.get_by_id(db, admission.requesting_doctor_id)
            if doctor and getattr(doctor, "fcm_token", None):
                send_notification(token=doctor.fcm_token, title="Admission request cancelled", body=body)
        except Exception as e:
            logger.error(f"Admission cancel notify failed: {e}")

        return ServiceResult.Success("Admission request cancelled.", updated)


    def _notify_role(self, db: Session, role: str, title: str, body: str):
        """
        Broadcasts a push notification to every user with the given role,
        same FCM pattern used elsewhere in the app (e.g. video call
        invites). Best-effort — a notification failure must never break
        the request/allocation flow itself.
        """
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
            logger.error(f"Admission notification failed: {e}")
