from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment


class DashboardRepository:

    def get_total_patients(
        self,
        db: Session,
    ) -> int:
        return db.query(Patient).count()

    def get_total_doctors(
        self,
        db: Session,
    ) -> int:
        return db.query(Doctor).count()

    def get_today_appointments(
        self,
        db: Session,
    ) -> int:
        return (
            db.query(Appointment)
            .filter(
                Appointment.appointment_date == date.today()
            )
            .count()
        )

    def get_status_count(
        self,
        db: Session,
        status: str,
    ) -> int:
        return (
            db.query(Appointment)
            .filter(
                Appointment.status == status
            )
            .count()
        )

    def get_recent_patients(
        self,
        db: Session,
        limit: int = 5,
    ):
        return (
            db.query(Patient)
            .order_by(
                Patient.id.desc()
            )
            .limit(limit)
            .all()
        )

    def get_available_doctors(
        self,
        db: Session,
    ):
        return (
            db.query(Doctor)
            .filter(
                Doctor.available == True
            )
            .all()
        )

    def get_upcoming_appointments(
        self,
        db: Session,
        limit: int = 10,
    ):
        return (
            db.query(Appointment)
            .filter(
                Appointment.appointment_date >= date.today()
            )
            .order_by(
                Appointment.appointment_date,
                Appointment.appointment_time,
            )
            .limit(limit)
            .all()
        )