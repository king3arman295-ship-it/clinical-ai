from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.repositories.base_repository import BaseRepository


class PatientRepository(BaseRepository[Patient]):

    def __init__(self):
        super().__init__(Patient)

    # -----------------------------------
    # Create Patient
    # -----------------------------------
    def create(
        self,
        db: Session,
        patient: Patient,
    ):
        db.add(patient)
        db.flush()
        db.refresh(patient)
        return patient

    # -----------------------------------
    # Get Patient By ID
    # -----------------------------------
    def get_by_id(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(Patient)
            .filter(
                Patient.id == patient_id
            )
            .first()
        )

    # -----------------------------------
    # Get Patient By Phone
    # -----------------------------------
    def get_by_phone(
        self,
        db: Session,
        phone: str,
    ):
        return (
            db.query(Patient)
            .filter(
                Patient.phone == phone
            )
            .first()
        )

    # -----------------------------------
    # Get Patient By Email
    # -----------------------------------
    def get_by_email(
        self,
        db: Session,
        email: str,
    ):
        return (
            db.query(Patient)
            .filter(
                Patient.email == email
            )
            .first()
        )

    # -----------------------------------
    # Search Patients By Name
    # -----------------------------------
    def search_by_name(
        self,
        db: Session,
        name: str,
    ):
        return (
            db.query(Patient)
            .filter(
                Patient.name.ilike(f"%{name}%")
            )
            .all()
        )

    # -----------------------------------
    # Get All Patients
    # -----------------------------------
    def get_all(
        self,
        db: Session,
    ):
        return (
            db.query(Patient)
            .order_by(Patient.name)
            .all()
        )

    # -----------------------------------
    # Update Patient
    # -----------------------------------
    def update(
        self,
        db: Session,
        patient: Patient,
    ):
        db.add(patient)
        db.flush()
        db.refresh(patient)
        return patient

    # -----------------------------------
    # Delete Patient
    # -----------------------------------
    def delete(
        self,
        db: Session,
        patient: Patient,
    ):
        db.delete(patient)
        db.flush()
    def update_fcm_token(
       self,
       db,
       patient_id: int,
       fcm_token: str,
    ):
      patient = (
        db.query(self.model)
        .filter(self.model.id == patient_id)
        .first()
    )

      if patient:
        patient.fcm_token = fcm_token
        db.flush()

      return patient   