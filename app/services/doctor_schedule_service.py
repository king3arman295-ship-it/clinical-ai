from sqlalchemy.orm import Session

from app.common.service_result import ServiceResult
from app.core.logger import logger
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    ConflictException,
)

from app.models.doctor_schedule import DoctorSchedule

from app.schemas.doctor_schedule import (
    DoctorScheduleCreate,
    DoctorScheduleUpdate,
)


class DoctorScheduleService:

    def __init__(
        self,
        doctor_repository,
        doctor_schedule_repository,
    ):
        self.doctor_repository = doctor_repository
        self.doctor_schedule_repository = (
            doctor_schedule_repository
        )

    # -----------------------------------
    # Create Schedule
    # -----------------------------------
    def create_schedule(
        self,
        db: Session,
        schedule: DoctorScheduleCreate,
    ) -> ServiceResult:

        doctor = self.doctor_repository.get_by_id(
            db,
            schedule.doctor_id,
        )

        if not doctor:
            raise NotFoundException(
                "Doctor not found."
            )

        existing = (
            self.doctor_schedule_repository
            .get_schedule_for_day(
                db,
                schedule.doctor_id,
                schedule.day_of_week,
            )
        )

        for item in existing:

            if (
                schedule.start_time < item.end_time
                and schedule.end_time > item.start_time
            ):
                raise ConflictException(
                    "This schedule overlaps with an existing schedule."
                )

        db_schedule = DoctorSchedule(
            doctor_id=schedule.doctor_id,
            day_of_week=schedule.day_of_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            slot_duration=schedule.slot_duration,
            is_available=schedule.is_available,
        )

        with UnitOfWork(db):

            created = (
                self.doctor_schedule_repository.create(
                    db,
                    db_schedule,
                )
            )

        logger.info(
            f"Doctor schedule created | ID={created.id}"
        )

        return ServiceResult.Success(
            "Doctor schedule created successfully.",
            created,
        )

    # -----------------------------------
    # Get All Schedules
    # -----------------------------------
    def get_all_schedules(
        self,
        db: Session,
    ) -> ServiceResult:

        schedules = (
            self.doctor_schedule_repository.get_all(
                db,
            )
        )

        return ServiceResult.Success(
            "Schedules retrieved successfully.",
            schedules,
        )

    # -----------------------------------
    # Get Schedule By ID
    # -----------------------------------
    def get_schedule_by_id(
        self,
        db: Session,
        schedule_id: int,
    ) -> ServiceResult:

        schedule = (
            self.doctor_schedule_repository.get_by_id(
                db,
                schedule_id,
            )
        )

        if not schedule:
            raise NotFoundException(
                "Schedule not found."
            )

        return ServiceResult.Success(
            "Schedule retrieved successfully.",
            schedule,
        )

    # -----------------------------------
    # Get Doctor Schedule
    # -----------------------------------
    def get_doctor_schedule(
        self,
        db: Session,
        doctor_id: int,
    ) -> ServiceResult:

        schedules = (
            self.doctor_schedule_repository.get_by_doctor(
                db,
                doctor_id,
            )
        )

        return ServiceResult.Success(
            "Doctor schedule retrieved successfully.",
            schedules,
        )

    # -----------------------------------
    # Update Schedule
    # -----------------------------------
    def update_schedule(
        self,
        db: Session,
        schedule_id: int,
        schedule_data: DoctorScheduleUpdate,
    ) -> ServiceResult:

        schedule = (
            self.doctor_schedule_repository.get_by_id(
                db,
                schedule_id,
            )
        )

        if not schedule:
            raise NotFoundException(
                "Schedule not found."
            )

        data = schedule_data.model_dump(
            exclude_unset=True
        )

        for key, value in data.items():
            setattr(schedule, key, value)

        with UnitOfWork(db):

            updated = (
                self.doctor_schedule_repository.update(
                    db,
                    schedule,
                )
            )

        logger.info(
            f"Doctor schedule updated | ID={updated.id}"
        )

        return ServiceResult.Success(
            "Doctor schedule updated successfully.",
            updated,
        )

    # -----------------------------------
    # Delete Schedule
    # -----------------------------------
    def delete_schedule(
        self,
        db: Session,
        schedule_id: int,
    ) -> ServiceResult:

        schedule = (
            self.doctor_schedule_repository.get_by_id(
                db,
                schedule_id,
            )
        )

        if not schedule:
            raise NotFoundException(
                "Schedule not found."
            )

        with UnitOfWork(db):

            self.doctor_schedule_repository.delete(
                db,
                schedule,
            )

        logger.info(
            f"Doctor schedule deleted | ID={schedule_id}"
        )

        return ServiceResult.Success(
            "Doctor schedule deleted successfully.",
            None,
        )
