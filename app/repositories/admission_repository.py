from sqlalchemy.orm import Session

from app.models.admission import Admission
from app.models.admission_note import AdmissionNote
from app.repositories.base_repository import BaseRepository
from app.common.enums import AdmissionStatus


class AdmissionRepository(BaseRepository[Admission]):

    def __init__(self):
        super().__init__(Admission)

    def create(self, db: Session, admission: Admission):
        db.add(admission)
        db.flush()
        db.refresh(admission)
        return admission

    def get_by_id(self, db: Session, admission_id: int):
        return (
            db.query(Admission)
            .filter(Admission.id == admission_id)
            .first()
        )

    def get_pending(self, db: Session):
        """Queue the Admission Head works from."""
        return (
            db.query(Admission)
            .filter(Admission.status == AdmissionStatus.PENDING.value)
            .order_by(Admission.requested_at)
            .all()
        )

    def get_active(self, db: Session):
        """All currently admitted (occupying a bed) patients."""
        return (
            db.query(Admission)
            .filter(Admission.status == AdmissionStatus.ADMITTED.value)
            .all()
        )

    def get_by_patient(self, db: Session, patient_id: int):
        return (
            db.query(Admission)
            .filter(Admission.patient_id == patient_id)
            .order_by(Admission.requested_at.desc())
            .all()
        )

    def get_by_doctor(self, db: Session, doctor_id: int):
        return (
            db.query(Admission)
            .filter(
                (Admission.requesting_doctor_id == doctor_id)
                | (Admission.admitting_doctor_id == doctor_id)
            )
            .order_by(Admission.requested_at.desc())
            .all()
        )

    def get_current_admission_for_patient(self, db: Session, patient_id: int):
        return (
            db.query(Admission)
            .filter(
                Admission.patient_id == patient_id,
                Admission.status == AdmissionStatus.ADMITTED.value,
            )
            .first()
        )

    def update(self, db: Session, admission: Admission):
        db.add(admission)
        db.flush()
        db.refresh(admission)
        return admission


class AdmissionNoteRepository(BaseRepository[AdmissionNote]):

    def __init__(self):
        super().__init__(AdmissionNote)

    def create(self, db: Session, note: AdmissionNote):
        db.add(note)
        db.flush()
        db.refresh(note)
        return note

    def get_by_admission(self, db: Session, admission_id: int):
        return (
            db.query(AdmissionNote)
            .filter(AdmissionNote.admission_id == admission_id)
            .order_by(AdmissionNote.created_at.desc())
            .all()
        )
