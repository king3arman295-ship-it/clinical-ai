from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate
)


def create_appointment(db: Session, appointment: AppointmentCreate):
    db_appointment = Appointment(
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_date=appointment.appointment_date,
        appointment_time=appointment.appointment_time,
        reason=appointment.reason,
        notes=appointment.notes
    )

    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)

    return db_appointment


def get_appointments(db: Session):
    return db.query(Appointment).all()


def get_appointment(db: Session, appointment_id: int):
    return (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )


def update_appointment(
    db: Session,
    appointment_id: int,
    appointment: AppointmentUpdate
):
    db_appointment = get_appointment(db, appointment_id)

    if not db_appointment:
        return None

    update_data = appointment.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_appointment, key, value)

    db.commit()
    db.refresh(db_appointment)

    return db_appointment


def delete_appointment(db: Session, appointment_id: int):
    db_appointment = get_appointment(db, appointment_id)

    if not db_appointment:
        return False

    db.delete(db_appointment)
    db.commit()

    return True