from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate


def create_patient(db: Session, patient: PatientCreate):
    db_patient = Patient(
        name=patient.name,
        phone=patient.phone,
        email=patient.email
    )

    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    return db_patient


def get_patients(db: Session):
    return db.query(Patient).all()


def get_patient(db: Session, patient_id: int):
    return db.query(Patient).filter(Patient.id == patient_id).first()


def update_patient(db: Session, patient_id: int, patient: PatientUpdate):
    db_patient = get_patient(db, patient_id)

    if not db_patient:
        return None

    data = patient.model_dump(exclude_unset=True)

    for key, value in data.items():
        setattr(db_patient, key, value)

    db.commit()
    db.refresh(db_patient)

    return db_patient


def delete_patient(db: Session, patient_id: int):
    db_patient = get_patient(db, patient_id)

    if not db_patient:
        return False

    db.delete(db_patient)
    db.commit()

    return True