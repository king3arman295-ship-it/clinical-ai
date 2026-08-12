from datetime import datetime

from app.services.firebase_service import send_notification
from app.core.logger import logger


class NotificationService:

    def __init__(self, appointment_repository):
        self.appointment_repository = appointment_repository

    def send_upcoming_video_notifications(
        self,
        db,
    ):
        appointments = (
            self.appointment_repository
            .get_upcoming_video_appointments(db)
        )

        sent_count = 0
        for appointment in appointments:
            # Mark as sent FIRST and commit immediately for this single
            # appointment. This closes the window where the same appointment
            # could be picked up again on the next scheduler tick (every 1
            # minute) before the previous commit went through, which is what
            # made the reminder appear to repeat every few minutes.
            appointment.notification_sent = True
            db.commit()

            # Compute the real minutes remaining instead of a hardcoded
            # "5 minutes" so the message stays accurate whenever it fires
            # inside the ~4-6 minute window (see get_upcoming_video_appointments).
            now = datetime.now()
            appt_dt = datetime.combine(appointment.appointment_date, appointment.appointment_time)
            minutes_left = max(0, round((appt_dt - now).total_seconds() / 60))
            time_phrase = "now" if minutes_left <= 1 else f"in about {minutes_left} minutes"

            patient_token = None
            doctor_token = None

            # 1. Patient FCM Token
            if appointment.patient and appointment.patient.fcm_token:
                patient_token = appointment.patient.fcm_token
            elif hasattr(appointment.patient, 'user') and appointment.patient and appointment.patient.user:
                patient_token = appointment.patient.user.fcm_token

            # 2. Doctor FCM Token
            if appointment.doctor and appointment.doctor.fcm_token:
                doctor_token = appointment.doctor.fcm_token
            elif hasattr(appointment.doctor, 'user') and appointment.doctor and appointment.doctor.user:
                doctor_token = appointment.doctor.user.fcm_token

            # Send Notification to Patient
            if patient_token:
                try:
                    send_notification(
                        token=patient_token,
                        title="📹 Video Consultation Starting Soon!",
                        body=f"Hello {appointment.patient.name}, your video consultation (Appointment #{appointment.id}) starts {time_phrase}!",
                    )
                    logger.info(f"Sent video consultation reminder to patient for Appointment #{appointment.id}")
                except Exception as e:
                    logger.error(f"Failed to send FCM notification to patient: {e}")

            # Send Notification to Doctor
            if doctor_token:
                try:
                    send_notification(
                        token=doctor_token,
                        title="📹 Video Consultation Starting Soon!",
                        body=f"Dr. {appointment.doctor.full_name}, your video consultation (Appointment #{appointment.id}) starts {time_phrase}!",
                    )
                    logger.info(f"Sent video consultation reminder to doctor for Appointment #{appointment.id}")
                except Exception as e:
                    logger.error(f"Failed to send FCM notification to doctor: {e}")

            sent_count += 1

        return sent_count