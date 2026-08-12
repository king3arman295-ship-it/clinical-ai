from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.doctor_schedule import (
    DoctorScheduleCreate,
    DoctorScheduleUpdate,
)

from app.services.doctor_schedule_service import (
    DoctorScheduleService,
)

from app.repositories.doctor_repository import DoctorRepository
from app.repositories.doctor_schedule_repository import (
    DoctorScheduleRepository,
)
from app.auth.roles import require_roles


router = APIRouter(
    prefix="/doctor-schedules",
    tags=["Doctor Schedules"],
)


def get_service():

    return DoctorScheduleService(
        doctor_repository=DoctorRepository(),
        doctor_schedule_repository=DoctorScheduleRepository(),
    )


# -----------------------------------
# Create Schedule
# -----------------------------------
@router.post("/")
def create_schedule(
    schedule: DoctorScheduleCreate,
    db: Session = Depends(get_db),
    service: DoctorScheduleService = Depends(get_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):
    if current_user["role"] == "doctor" and schedule.doctor_id != current_user.get("doctor_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own schedule.")

    result = service.create_schedule(
        db,
        schedule,
    )

    return result.data


# -----------------------------------
# Get All Schedules
# -----------------------------------
@router.get("/")
def get_all_schedules(
    db: Session = Depends(get_db),
    service: DoctorScheduleService = Depends(get_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):

    result = service.get_all_schedules(db)

    return result.data


# -----------------------------------
# Get Doctor Schedule
# -----------------------------------
@router.get("/doctor/{doctor_id}")
def get_doctor_schedule(
    doctor_id: int,
    db: Session = Depends(get_db),
    service: DoctorScheduleService = Depends(get_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):

    result = service.get_doctor_schedule(
        db,
        doctor_id,
    )

    return result.data


# -----------------------------------
# Get Schedule By ID
# -----------------------------------
@router.get("/{schedule_id}")
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    service: DoctorScheduleService = Depends(get_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):

    result = service.get_schedule_by_id(
        db,
        schedule_id,
    )

    return result.data


# -----------------------------------
# Update Schedule
# -----------------------------------
@router.put("/{schedule_id}")
def update_schedule(
    schedule_id: int,
    schedule: DoctorScheduleUpdate,
    db: Session = Depends(get_db),
    service: DoctorScheduleService = Depends(get_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):
    if current_user["role"] == "doctor":
        existing = service.get_schedule_by_id(db, schedule_id).data
        if existing.doctor_id != current_user.get("doctor_id"):
            raise HTTPException(status_code=403, detail="You can only manage your own schedule.")
        if schedule.doctor_id is not None and schedule.doctor_id != current_user.get("doctor_id"):
            raise HTTPException(status_code=403, detail="You cannot reassign a schedule to another doctor.")

    result = service.update_schedule(
        db,
        schedule_id,
        schedule,
    )

    return result.data


# -----------------------------------
# Delete Schedule
# -----------------------------------
@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    service: DoctorScheduleService = Depends(get_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):
    if current_user["role"] == "doctor":
        existing = service.get_schedule_by_id(db, schedule_id).data
        if existing.doctor_id != current_user.get("doctor_id"):
            raise HTTPException(status_code=403, detail="You can only manage your own schedule.")

    result = service.delete_schedule(
        db,
        schedule_id,
    )

    return {
        "message": result.message,
    }
