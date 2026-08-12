from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

import app.models
from app.core.database import SessionLocal
from app.repositories.appointment_repository import AppointmentRepository
from app.services.notification_service import NotificationService
from app.core.logger import logger

scheduler = BackgroundScheduler()


def check_video_appointments():
    logger.info(
        f"[Scheduler] Checking appointments at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    db = SessionLocal()
    try:
        service = NotificationService(AppointmentRepository())
        sent_count = service.send_upcoming_video_notifications(db)
        if sent_count > 0:
            logger.info(f"[Scheduler] Sent {sent_count} video appointment notification(s).")
    except Exception as e:
        logger.error(f"[Scheduler] Error in appointment scheduler: {e}")
    finally:
        db.close()


def start_scheduler():

    scheduler.add_job(
        check_video_appointments,
        IntervalTrigger(minutes=1),
        id="video_appointment_checker",
        replace_existing=True,
    )

    scheduler.start()

    logger.info("[Scheduler] Appointment Scheduler Started")
