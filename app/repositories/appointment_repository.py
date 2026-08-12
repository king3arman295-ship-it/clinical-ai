from datetime import date, time

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.repositories.base_repository import BaseRepository
from datetime import datetime, timedelta

from app.common.enums import (
    AppointmentType,
    AppointmentStatus,
)


class AppointmentRepository(BaseRepository[Appointment]):

    def __init__(self):
        super().__init__(Appointment)

    # -----------------------------------
    # Create
    # -----------------------------------
    def create(
        self,
        db: Session,
        appointment: Appointment,
    ):
        db.add(appointment)
        db.flush()
        db.refresh(appointment)
        return appointment

    # -----------------------------------
    # Check if slot already booked
    # -----------------------------------
    def slot_exists(
        self,
        db: Session,
        doctor_id: int,
        appointment_date: date,
        appointment_time: time,
    ):
        return (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == appointment_date,
                Appointment.appointment_time == appointment_time,
                Appointment.status == AppointmentStatus.SCHEDULED,
            )
            .first()
        )

    # -----------------------------------
    # Get all appointments
    # -----------------------------------
    def get_all(
        self,
        db: Session,
    ):
        return (
            db.query(Appointment)
            .all()
        )

    # -----------------------------------
    # Get appointment by ID
    # -----------------------------------
    def get_by_id(
        self,
        db: Session,
        appointment_id: int,
    ):
        return (
            db.query(Appointment)
            .filter(
                Appointment.id == appointment_id
            )
            .first()
        )

    # -----------------------------------
    # Get doctor's appointments on a date
    # -----------------------------------
    def get_doctor_schedule(
        self,
        db: Session,
        doctor_id: int,
        appointment_date: date,
    ):
        return (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == appointment_date,
                Appointment.status == AppointmentStatus.SCHEDULED,
            )
            .order_by(
                Appointment.appointment_time
            )
            .all()
        )

    # -----------------------------------
    # Get patient's appointments
    # -----------------------------------
    def get_patient_appointments(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(Appointment)
            .filter(
                Appointment.patient_id == patient_id
            )
            .order_by(
                Appointment.appointment_date.desc(),
                Appointment.appointment_time.desc(),
            )
            .all()
        )

    # -----------------------------------
    # Get doctor's appointments
    # -----------------------------------
    def get_doctor_appointments(
        self,
        db: Session,
        doctor_id: int,
    ):
        return (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id
            )
            .order_by(
                Appointment.appointment_date.desc(),
                Appointment.appointment_time.desc(),
            )
            .all()
        )

    # -----------------------------------
    # Update
    # -----------------------------------
    def update(
        self,
        db: Session,
        appointment: Appointment,
    ):
        db.add(appointment)
        db.flush()
        db.refresh(appointment)
        return appointment
    # ---------------------------------------------------------
# Get Video Meeting Details
# ---------------------------------------------------------

    def get_video_details(
     self,
     db: Session,
     appointment_id: int,
    ):

        return (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id
        )
        .first()
       )
    # -----------------------------------
    # Delete
    # -----------------------------------
    def delete(
        self,
        db: Session,
        appointment: Appointment,
    ):
        db.delete(appointment)
        db.flush()
    def get_upcoming_video_appointments(
        self,
        db,
    ):
        now = datetime.now()
        # Reminder should go out ~5 minutes before the session. The scheduler
        # ticks every 1 minute, so a band of 4-6 minutes out guarantees the
        # appointment is picked up on some tick right around the 5-minute
        # mark — narrow enough to still read as "5 minutes before", but wide
        # enough that a slow tick can't skip over it entirely. The lower
        # bound also matters: without one, any already-elapsed appointment
        # still marked notification_sent=False (e.g. one nobody joined) would
        # match on every subsequent tick, which is what caused reminders to
        # keep firing long after they were first due instead of exactly once.
        window_start = (now + timedelta(minutes=4)).time()
        window_end = (now + timedelta(minutes=6)).time()

        return (
            db.query(self.model)
            .filter(
                self.model.notification_sent == False,
                self.model.appointment_type == AppointmentType.VIDEO,
                self.model.status == AppointmentStatus.SCHEDULED,
                self.model.appointment_date == now.date(),
                self.model.appointment_time >= window_start,
                self.model.appointment_time <= window_end,
            )
            .all()
        )

    def save_patient_fcm_token(
    self,
    db,
    appointment_id: int,
    fcm_token: str,
):
      appointment = (
        db.query(self.model)
        .filter(self.model.id == appointment_id)
        .first()
    )

      if appointment:
        appointment.patient.fcm_token = fcm_token
        db.flush()

      return appointment


    def save_doctor_fcm_token(
    self,
    db,
    appointment_id: int,
    fcm_token: str,
):
      appointment = (
        db.query(self.model)
        .filter(self.model.id == appointment_id)
        .first()
    )

      if appointment:
        appointment.doctor.fcm_token = fcm_token
        db.flush()

      return appointment