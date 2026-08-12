from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.common.messages import Messages
from app.common.service_result import ServiceResult

from app.core.logger import logger
from app.core.timezone import now
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    ConflictException,
    BadRequestException,
)

from app.models.appointment import Appointment

from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
)

from app.common.enums import (
    AppointmentStatus,
    MeetingStatus,
)

from app.integrations.agora_service import AgoraService
from app.services.firebase_service import send_notification


class AppointmentService:

    def __init__(
        self,
        patient_repository,
        doctor_repository,
        doctor_schedule_repository,
        appointment_repository,
    ):
        self.patient_repository = patient_repository
        self.doctor_repository = doctor_repository
        self.doctor_schedule_repository = doctor_schedule_repository
        self.appointment_repository = appointment_repository

        self.agora_service = AgoraService()

    # -------------------------------------------------
    # Book Appointment
    # -------------------------------------------------

    def book_appointment(
        self,
        db: Session,
        appointment: AppointmentCreate,
    ) -> ServiceResult:

        # ---------------------------------------
        # Check Patient Exists
        # ---------------------------------------

        patient = self.patient_repository.get_by_id(
            db,
            appointment.patient_id,
        )

        if not patient:
            raise NotFoundException(
                Messages.PATIENT_NOT_FOUND
            )

        # ---------------------------------------
        # Check Doctor Exists
        # ---------------------------------------

        doctor = self.doctor_repository.get_available_doctor(
            db,
            appointment.doctor_id,
        )

        if not doctor:
            raise BadRequestException(
                Messages.DOCTOR_UNAVAILABLE
            )

        # ---------------------------------------
        # Cannot Book In Past
        # ---------------------------------------

        appointment_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time,
        )

        if appointment_datetime < now():
            raise BadRequestException(
                Messages.APPOINTMENT_IN_PAST
            )

        # ---------------------------------------
        # Doctor Schedule
        # ---------------------------------------

        day_name = appointment.appointment_date.strftime("%A")

        schedule = self.doctor_schedule_repository.get_schedule(
            db=db,
            doctor_id=appointment.doctor_id,
            day_of_week=day_name,
        )

        if not schedule:
            raise BadRequestException(
                f"{doctor.full_name} does not work on {day_name}."
            )

        # ---------------------------------------
        # Doctor Availability
        # ---------------------------------------

        if not schedule.is_available:
            raise BadRequestException(
                f"{doctor.full_name} is unavailable on {day_name}."
            )

        # ---------------------------------------
        # Check Working Hours
        # ---------------------------------------

        if (
            appointment.appointment_time < schedule.start_time
            or appointment.appointment_time >= schedule.end_time
        ):
            raise BadRequestException(
                f"{doctor.full_name} is available only between "
                f"{schedule.start_time.strftime('%H:%M')} and "
                f"{schedule.end_time.strftime('%H:%M')}."
            )

        # ---------------------------------------
        # Check Slot Interval
        # ---------------------------------------

        minutes = (
            appointment.appointment_time.hour * 60
            + appointment.appointment_time.minute
        )

        start_minutes = (
            schedule.start_time.hour * 60
            + schedule.start_time.minute
        )

        if (
            (minutes - start_minutes)
            % schedule.slot_duration
            != 0
        ):
            raise BadRequestException(
                f"Appointments must be booked every "
                f"{schedule.slot_duration} minutes."
            )

        # ---------------------------------------
        # Check Existing Appointment
        # ---------------------------------------

        existing = self.appointment_repository.slot_exists(
            db,
            appointment.doctor_id,
            appointment.appointment_date,
            appointment.appointment_time,
        )

        if existing:
            raise ConflictException(
                Messages.SLOT_ALREADY_BOOKED
            )
                # ---------------------------------------
        # Generate Video Meeting Details
        # ---------------------------------------

        video_channel = None
        meeting_status = MeetingStatus.SCHEDULED

        appt_type_str = appointment.appointment_type.value if hasattr(appointment.appointment_type, "value") else str(appointment.appointment_type)

        if appt_type_str.lower() == "video":
            video_channel = self.agora_service.generate_channel_name(
                appointment.patient_id
            )

        # ---------------------------------------
        # Save Appointment
        # ---------------------------------------

        db_appointment = Appointment(
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            appointment_date=appointment.appointment_date,
            appointment_time=appointment.appointment_time,
            appointment_type=appointment.appointment_type,
            status=AppointmentStatus.SCHEDULED,
            meeting_status=meeting_status,
            video_channel=video_channel,
            reason=appointment.reason,
            notes=appointment.notes,
        )

        with UnitOfWork(db):
            booked = self.appointment_repository.create(
                db,
                db_appointment,
            )

        logger.info(
            f"Appointment booked | "
            f"ID={booked.id} | "
            f"Patient={booked.patient_id} | "
            f"Doctor={booked.doctor_id}"
        )

        return ServiceResult.Success(
            Messages.APPOINTMENT_CREATED,
            booked,
        )

    # -------------------------------------------------
    # Get All Appointments
    # -------------------------------------------------

    def get_all_appointments(
        self,
        db: Session,
    ) -> ServiceResult:

        appointments = self.appointment_repository.get_all(
            db
        )

        return ServiceResult.Success(
            "Appointments retrieved successfully.",
            appointments,
        )

    # -------------------------------------------------
    # Get Patient's Own Appointments
    # -------------------------------------------------

    def get_my_appointments(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        appointments = self.appointment_repository.get_patient_appointments(
            db,
            patient_id,
        )

        return ServiceResult.Success(
            "Appointments retrieved successfully.",
            appointments,
        )

    # -------------------------------------------------
    # Get Appointment By ID
    # -------------------------------------------------

    def get_appointment_by_id(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        appointment = self.appointment_repository.get_by_id(
            db,
            appointment_id,
        )

        if not appointment:
            raise NotFoundException(
                "Appointment not found."
            )

        return ServiceResult.Success(
            "Appointment retrieved successfully.",
            appointment,
        )
        # -------------------------------------------------
    # Update Appointment
    # -------------------------------------------------

    def update_appointment(
        self,
        db: Session,
        appointment_id: int,
        appointment_data: AppointmentUpdate,
    ) -> ServiceResult:

        appointment = self.appointment_repository.get_by_id(
            db,
            appointment_id,
        )

        if not appointment:
            raise NotFoundException(
                "Appointment not found."
            )

        data = appointment_data.model_dump(
            exclude_unset=True
        )

        # ---------------------------------------
        # Reset Stale Call State On Reschedule
        # ---------------------------------------
        # If the date and/or time is changing, this is effectively a new
        # meeting slot — any leftover LIVE/COMPLETED status, start/end
        # timestamps, or duration from a previous session (e.g. a call
        # that was joined but never explicitly ended) must not carry over.
        # Without this, a stale LIVE flag from an old, forgotten session
        # would keep bypassing the past-date check on the new date forever.
        is_rescheduled = (
            "appointment_date" in data and data["appointment_date"] != appointment.appointment_date
        ) or (
            "appointment_time" in data and data["appointment_time"] != appointment.appointment_time
        )

        if is_rescheduled and appointment.appointment_type.value == "video":
            data.setdefault("meeting_status", MeetingStatus.SCHEDULED)
            data["meeting_started_at"] = None
            data["meeting_ended_at"] = None
            data["call_duration"] = None

        # ---------------------------------------
        # Update Fields
        # ---------------------------------------

        for key, value in data.items():
            setattr(
                appointment,
                key,
                value,
            )

        # ---------------------------------------
        # Save Changes
        # ---------------------------------------

        with UnitOfWork(db):
            updated = self.appointment_repository.update(
                db,
                appointment,
            )

        logger.info(
            f"Appointment updated | ID={updated.id}"
        )

        return ServiceResult.Success(
            "Appointment updated successfully.",
            updated,
        )

    # -------------------------------------------------
    # Join Video Meeting
    # -------------------------------------------------

    def _ensure_joinable_video(self, appointment) -> None:
        """Raise if the appointment can't be joined for a video call.

        Rejects non-video, cancelled/completed, and past appointments (a LIVE
        meeting keeps working even if its scheduled time has passed — but
        only for a bounded window, see MAX_LIVE_HOURS below. Without that
        cap, an appointment that was joined once and never properly ended
        — closed tab, crash, dropped connection — stays "LIVE" forever and
        would bypass the past-date check indefinitely, even after being
        rescheduled to a completely different date.)
        """
        from datetime import datetime as dt, timezone as tz

        # A real consultation call is a handful of minutes to an hour or
        # two at most. Anything still marked LIVE after this long was
        # clearly never ended properly and shouldn't keep exempting the
        # appointment from the past-date check.
        MAX_LIVE_HOURS = 4

        if not appointment:
            raise NotFoundException("Appointment not found.")

        if appointment.appointment_type.value != "video":
            raise BadRequestException("This appointment is not a video consultation.")

        if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED):
            raise BadRequestException("This appointment has been cancelled or completed.")

        is_genuinely_live = False
        if appointment.meeting_status == MeetingStatus.LIVE:
            started_at = appointment.meeting_started_at
            if started_at is None:
                # Marked LIVE with no start timestamp shouldn't happen, but
                # if it does, don't trust it as a live-call exemption.
                is_genuinely_live = False
            else:
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=tz.utc)
                age_hours = (dt.now(tz.utc) - started_at).total_seconds() / 3600
                is_genuinely_live = age_hours <= MAX_LIVE_HOURS

        appt_dt = dt.combine(appointment.appointment_date, appointment.appointment_time)
        if appt_dt < now() and not is_genuinely_live:
            raise BadRequestException(
                "This video appointment has already passed and can no longer be joined."
            )

    def join_video_meeting(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        appointment = self.appointment_repository.get_by_id(
            db,
            appointment_id,
        )

        self._ensure_joinable_video(appointment)

        uid = self.agora_service.generate_uid()

        token = self.agora_service.generate_token(
            channel_name=appointment.video_channel,
            uid=uid,
        )

        if appointment.meeting_started_at is None:

            appointment.meeting_started_at = datetime.now(
                timezone.utc
            )

            appointment.meeting_status = (
                MeetingStatus.LIVE
            )

            with UnitOfWork(db):
                self.appointment_repository.update(
                    db,
                    appointment,
                )

        return ServiceResult.Success(
            "Meeting joined successfully.",
            {
                "appointment_id": appointment.id,
                "app_id": self.agora_service.app_id,
                "channel": appointment.video_channel,
                "token": token,
                "uid": uid,
            },
        )
    
        # -------------------------------------------------
    # End Video Meeting
    # -------------------------------------------------

    def end_video_meeting(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        appointment = self.appointment_repository.get_by_id(
            db,
            appointment_id,
        )

        if not appointment:
            raise NotFoundException(
                "Appointment not found."
            )

        if appointment.appointment_type.value != "video":
            raise BadRequestException(
                "This appointment is not a video consultation."
            )

        if appointment.meeting_started_at is None:
            raise BadRequestException(
                "Meeting has not started."
            )

        # ---------------------------------------
        # Handle timezone mismatch
        # ---------------------------------------

        started_at = appointment.meeting_started_at

        if started_at.tzinfo is None:
            started_at = started_at.replace(
                tzinfo=timezone.utc
            )

        appointment.meeting_ended_at = datetime.now(
            timezone.utc
        )

        duration = (
            appointment.meeting_ended_at
            - started_at
        )

        appointment.call_duration = int(
            duration.total_seconds()
        )

        appointment.meeting_status = (
            MeetingStatus.COMPLETED
        )

        appointment.status = (
            AppointmentStatus.COMPLETED
        )

        with UnitOfWork(db):
            updated = self.appointment_repository.update(
                db,
                appointment,
            )

        logger.info(
            f"Meeting ended | Appointment={updated.id}"
        )

        return ServiceResult.Success(
            "Meeting ended successfully.",
            updated,
        )
        # -------------------------------------------------
    # Delete Appointment
    # -------------------------------------------------

    # -------------------------------------------------
    # Cancel Appointment (Patient self-service)
    # -------------------------------------------------

    def cancel_appointment(
        self,
        db: Session,
        appointment_id: int,
        patient_id: int,
    ) -> ServiceResult:

        appointment = self.appointment_repository.get_by_id(
            db,
            appointment_id,
        )

        if not appointment:
            raise NotFoundException(
                "Appointment not found."
            )

        if appointment.patient_id != patient_id:
            raise BadRequestException(
                "You can only cancel your own appointments."
            )

        if appointment.status == AppointmentStatus.CANCELLED:
            raise ConflictException(
                "This appointment is already cancelled."
            )

        if appointment.status == AppointmentStatus.COMPLETED:
            raise ConflictException(
                "A completed appointment cannot be cancelled."
            )

        appointment.status = AppointmentStatus.CANCELLED
        appointment.meeting_status = MeetingStatus.CANCELLED

        with UnitOfWork(db):
            updated = self.appointment_repository.update(
                db,
                appointment,
            )

        logger.info(
            f"Appointment cancelled by patient | ID={updated.id} | patient_id={patient_id}"
        )

        return ServiceResult.Success(
            "Appointment cancelled successfully.",
            updated,
        )

    # -------------------------------------------------
    # Delete Appointment
    # -------------------------------------------------

    def delete_appointment(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        appointment = self.appointment_repository.get_by_id(
            db,
            appointment_id,
        )

        if not appointment:
            raise NotFoundException(
                "Appointment not found."
            )

        with UnitOfWork(db):
            self.appointment_repository.delete(
                db,
                appointment,
            )

        logger.info(
            f"Appointment deleted | ID={appointment_id}"
        )

        return ServiceResult.Success(
            "Appointment deleted successfully.",
            None,
        )
    # -------------------------------------------------
# Get Video Meeting Details
# -------------------------------------------------

    def get_video_details(
     self,
     db: Session,
    appointment_id: int,
    ) -> ServiceResult:

      appointment = self.appointment_repository.get_video_details(
        db,
        appointment_id,
    )

    # ---------------------------------------
    # Appointment Exists
    # ---------------------------------------

      if not appointment:
        raise NotFoundException(
            "Appointment not found."
        )

    # ---------------------------------------
    # Must Be Video Appointment
    # ---------------------------------------

      if appointment.appointment_type != "video":
        raise BadRequestException(
            "This appointment is not a video consultation."
        )

    # ---------------------------------------
    # Video Channel Must Exist
    # ---------------------------------------

      if not appointment.video_channel:
        raise BadRequestException(
            "Video meeting has not been created."
        )

    # ---------------------------------------
    # Response
    # ---------------------------------------

      return ServiceResult.Success(
        "Video meeting details retrieved successfully.",
        {
            "appointment_id": appointment.id,
            "doctor_id": appointment.doctor_id,
            "patient_id": appointment.patient_id,
            "appointment_date": appointment.appointment_date,
            "appointment_time": appointment.appointment_time,
            "appointment_type": appointment.appointment_type,
            "meeting_status": appointment.meeting_status,
            "channel": appointment.video_channel,
        },
    )
    # -------------------------------------------------
# Doctor Join Video Meeting
# -------------------------------------------------

    def join_doctor_meeting(
     self,
     db: Session,
     appointment_id: int,
    ) -> ServiceResult:

      appointment = self.appointment_repository.get_by_id(
        db,
        appointment_id,
    )

      self._ensure_joinable_video(appointment)

      if appointment.meeting_started_at is None:
          appointment.meeting_started_at = datetime.now(timezone.utc)
          appointment.meeting_status = MeetingStatus.LIVE
          with UnitOfWork(db):
              self.appointment_repository.update(db, appointment)

      uid = self.agora_service.generate_uid()

      token = self.agora_service.generate_token(
        channel_name=appointment.video_channel,
        uid=uid,
        role=1,
    )

      return ServiceResult.Success(
        "Doctor joined successfully.",
        {
            "appointment_id": appointment.id,
            "app_id": self.agora_service.app_id,
            "channel": appointment.video_channel,
            "token": token,
            "uid": uid,
            "role": "doctor",
        },
    )
    # -------------------------------------------------
# Patient Join Video Meeting
# -------------------------------------------------

    def join_patient_meeting(
    self,
    db: Session,
    appointment_id: int,
    ) -> ServiceResult:

      appointment = self.appointment_repository.get_by_id(
        db,
        appointment_id,
    )

      self._ensure_joinable_video(appointment)

      if appointment.meeting_started_at is None:
          appointment.meeting_started_at = datetime.now(timezone.utc)
          appointment.meeting_status = MeetingStatus.LIVE
          with UnitOfWork(db):
              self.appointment_repository.update(db, appointment)

      uid = self.agora_service.generate_uid()

      token = self.agora_service.generate_token(
        channel_name=appointment.video_channel,
        uid=uid,
        role=2,   # Subscriber / Patient
    )

      return ServiceResult.Success(
        "Patient joined successfully.",
        {
            "appointment_id": appointment.id,
            "app_id": self.agora_service.app_id,
            "channel": appointment.video_channel,
            "token": token,
            "uid": uid,
            "role": "patient",
        },
    )
    def save_patient_fcm_token(
    self,
    db,
    appointment_id: int,
    fcm_token: str,
):
      with UnitOfWork(db):
        appointment = (
            self.appointment_repository
            .save_patient_fcm_token(
                db,
                appointment_id,
                fcm_token,
            )
        )

      return ServiceResult.Success(
        "Patient FCM token saved successfully.",
        appointment,
    )


    def save_doctor_fcm_token(
    self,
    db,
    appointment_id: int,
    fcm_token: str,
):
      with UnitOfWork(db):
        appointment = (
            self.appointment_repository
            .save_doctor_fcm_token(
                db,
                appointment_id,
                fcm_token,
            )
        )

      return ServiceResult.Success(
        "Doctor FCM token saved successfully.",
        appointment,
    )

    # -------------------------------------------------
    # Notify Patient Of Incoming Video Call
    # -------------------------------------------------
    # Fired the moment the doctor starts the call (from the "join/doctor"
    # flow). The patient never has a "start call" button of their own —
    # this push, shown as a call-style notification with Accept/Decline
    # actions (see firebase-messaging-sw.js), is the only way they find
    # out a call has started and the only way into the meeting.

    def notify_incoming_call(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        appointment = self.appointment_repository.get_by_id(
            db,
            appointment_id,
        )

        if not appointment:
            raise NotFoundException("Appointment not found.")

        patient_token = None
        if appointment.patient and appointment.patient.fcm_token:
            patient_token = appointment.patient.fcm_token

        if not patient_token:
            logger.warning(
                f"No patient FCM token on file for Appointment #{appointment_id}; "
                "call started without an incoming-call push."
            )
            return ServiceResult.Success(
                "Call started. Patient has no notification token on file.",
                {"notified": False},
            )

        doctor_name = (
            appointment.doctor.full_name if appointment.doctor else "Your doctor"
        )

        try:
            sent = send_notification(
                token=patient_token,
                data={
                    "type": "incoming_call",
                    "appointment_id": appointment.id,
                    "doctor_name": doctor_name,
                },
            )
        except Exception as e:
            logger.error(f"Failed to send incoming call push: {e}")
            return ServiceResult.Success(
                "Call started. Push notification failed to send.",
                {"notified": False},
            )

        if sent is None:
            # send_notification returns None (no exception) when Firebase
            # Admin was never initialized — e.g. firebase/service-account.json
            # is missing. This used to be reported as a false "notified: true".
            logger.warning(
                f"Incoming call push for Appointment #{appointment_id} was not "
                "sent: Firebase Admin SDK is not initialized on this server."
            )
            return ServiceResult.Success(
                "Call started. Firebase is not configured on the server, so no push was sent.",
                {"notified": False},
            )

        logger.info(f"Sent incoming call push for Appointment #{appointment_id}")
        return ServiceResult.Success(
            "Incoming call notification sent to patient.",
            {"notified": True},
        )