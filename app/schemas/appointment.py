from datetime import date, time, datetime

from pydantic import BaseModel, ConfigDict

from app.common.enums import (
    AppointmentType,
    AppointmentStatus,
    MeetingStatus,
)


# ---------------------------------------------------------
# Create Appointment
# ---------------------------------------------------------
class AppointmentCreate(BaseModel):
    patient_id: int | None = None
    doctor_id: int

    appointment_date: date
    appointment_time: time

    appointment_type: AppointmentType = AppointmentType.PHYSICAL

    reason: str | None = None
    notes: str | None = None


# ---------------------------------------------------------
# Update Appointment
# ---------------------------------------------------------
class AppointmentUpdate(BaseModel):
    appointment_date: date | None = None
    appointment_time: time | None = None

    appointment_type: AppointmentType | None = None

    status: AppointmentStatus | None = None

    reason: str | None = None
    notes: str | None = None

# ---------------------------------------------------------
# Video Meeting Details Response
# ---------------------------------------------------------

class VideoMeetingDetailsResponse(BaseModel):
    appointment_id: int

    doctor_id: int
    patient_id: int

    appointment_date: date
    appointment_time: time

    appointment_type: AppointmentType

    meeting_status: MeetingStatus

    channel: str

    model_config = ConfigDict(
        from_attributes=True
    )
# ---------------------------------------------------------
# Appointment Response
# ---------------------------------------------------------
class AppointmentResponse(BaseModel):
    id: int

    patient_id: int
    doctor_id: int

    appointment_date: date
    appointment_time: time

    appointment_type: AppointmentType

    status: AppointmentStatus

    meeting_status: MeetingStatus

    video_channel: str | None

    meeting_started_at: datetime | None

    meeting_ended_at: datetime | None

    call_duration: int | None

    reason: str | None

    notes: str | None

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )
class FCMTokenRequest(BaseModel):
    fcm_token: str