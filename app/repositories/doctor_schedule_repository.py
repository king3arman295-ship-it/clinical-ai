from sqlalchemy.orm import Session

from app.models.doctor_schedule import DoctorSchedule
from app.repositories.base_repository import BaseRepository


class DoctorScheduleRepository(
    BaseRepository[DoctorSchedule]
):

    def __init__(self):
        super().__init__(DoctorSchedule)

    # -----------------------------------
    # Get Doctor Schedule
    # -----------------------------------
    def get_schedule(
        self,
        db: Session,
        doctor_id: int,
        day_of_week: str,
    ):
        return (
            db.query(DoctorSchedule)
            .filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.day_of_week == day_of_week,
                DoctorSchedule.is_available.is_(True),
            )
            .first()
        )

    # -----------------------------------
    # Get Schedule For Day
    # -----------------------------------
    def get_schedule_for_day(
    self,
    db: Session,
    doctor_id: int,
    day_of_week: str,
):
     return (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.day_of_week == day_of_week,
        )
        .all()
    )
    # -----------------------------------
    # Get All Schedules
    # -----------------------------------
    def get_all(
        self,
        db: Session,
    ):
        return (
            db.query(DoctorSchedule)
            .all()
        )

    # -----------------------------------
    # Get Schedule By ID
    # -----------------------------------
    def get_by_id(
        self,
        db: Session,
        schedule_id: int,
    ):
        return (
            db.query(DoctorSchedule)
            .filter(
                DoctorSchedule.id == schedule_id,
            )
            .first()
        )

    # -----------------------------------
    # Get Doctor Schedules
    # -----------------------------------
    def get_by_doctor(
        self,
        db: Session,
        doctor_id: int,
    ):
        return (
            db.query(DoctorSchedule)
            .filter(
                DoctorSchedule.doctor_id == doctor_id,
            )
            .all()
        )

    # -----------------------------------
    # Update Schedule
    # -----------------------------------
    def update(
        self,
        db: Session,
        schedule: DoctorSchedule,
    ):
        db.add(schedule)
        db.flush()
        db.refresh(schedule)
        return schedule

    # -----------------------------------
    # Delete Schedule
    # -----------------------------------
    def delete(
        self,
        db: Session,
        schedule: DoctorSchedule,
    ):
        db.delete(schedule)
        db.flush()