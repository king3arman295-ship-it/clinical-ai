from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from app.core.database import SessionLocal
from app.core.logger import logger

scheduler = BackgroundScheduler()


def check_medicine_dose_reminders():
    logger.info(
        f"[MedReminder] Checking doses at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    db = SessionLocal()
    try:
        from app.services.nursing_service import NursingService
        from app.repositories.nursing_repository import (
            MedicationCourseRepository,
            MedicationCourseItemRepository,
            MedicationCourseDoseRepository,
            NurseBedAssignmentRepository,
        )
        service = NursingService(
            assignment_repo=NurseBedAssignmentRepository(),
            course_repo=MedicationCourseRepository(),
            item_repo=MedicationCourseItemRepository(),
            dose_repo=MedicationCourseDoseRepository(),
        )
        sent = service.send_upcoming_patient_dose_reminders(db, window_minutes=10)
        if sent:
            logger.info(f"[MedReminder] Sent {sent} patient dose reminder(s).")
    except Exception as e:
        logger.error(f"[MedReminder] Error: {e}")
    finally:
        db.close()


def start_medicine_reminder_scheduler():
    scheduler.add_job(
        check_medicine_dose_reminders,
        IntervalTrigger(minutes=1),
        id="medicine_dose_reminder_checker",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("[MedReminder] Medicine dose reminder scheduler started")
