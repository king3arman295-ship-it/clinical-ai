from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.schemas.doctor import DoctorCreate, DoctorUpdate


def create_doctor(db: Session, doctor: DoctorCreate):
    db_doctor = Doctor(
        full_name=doctor.full_name,
        specialization=doctor.specialization,
        qualification=doctor.qualification,
        phone=doctor.phone,
        email=doctor.email,
        consultation_fee=doctor.consultation_fee,
        experience_years=doctor.experience_years,
        available=doctor.available
    )

    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)

    return db_doctor


def get_doctors(db: Session):
    return db.query(Doctor).all()


def get_doctor(db: Session, doctor_id: int):
    return db.query(Doctor).filter(Doctor.id == doctor_id).first()


def update_doctor(db: Session, doctor_id: int, doctor: DoctorUpdate):
    db_doctor = get_doctor(db, doctor_id)

    if not db_doctor:
        return None

    update_data = doctor.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_doctor, key, value)

    db.commit()
    db.refresh(db_doctor)

    return db_doctor


def delete_doctor(db: Session, doctor_id: int):
    db_doctor = get_doctor(db, doctor_id)

    if not db_doctor:
        return False

    db.delete(db_doctor)
    db.commit()

    return True