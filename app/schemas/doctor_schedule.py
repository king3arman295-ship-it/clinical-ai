from datetime import time

from pydantic import BaseModel, ConfigDict


# -----------------------------------
# Create Doctor Schedule
# -----------------------------------
class DoctorScheduleCreate(BaseModel):
    doctor_id: int
    day_of_week: str
    start_time: time
    end_time: time
    slot_duration: int = 30
    is_available: bool = True


# -----------------------------------
# Update Doctor Schedule
# -----------------------------------
class DoctorScheduleUpdate(BaseModel):
    doctor_id: int | None = None
    day_of_week: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    slot_duration: int | None = None
    is_available: bool | None = None


# -----------------------------------
# Doctor Schedule Response
# -----------------------------------
class DoctorScheduleResponse(BaseModel):
    id: int
    doctor_id: int
    day_of_week: str
    start_time: time
    end_time: time
    slot_duration: int
    is_available: bool

    model_config = ConfigDict(
        from_attributes=True
    )