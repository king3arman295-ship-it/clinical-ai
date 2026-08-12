from sqlalchemy.orm import Session

from app.common.service_result import ServiceResult
from app.core.logger import logger


class DashboardService:

    def __init__(
        self,
        dashboard_repository,
    ):
        self.dashboard_repository = dashboard_repository

    # -------------------------------------------------
    # Dashboard Statistics
    # -------------------------------------------------

    def get_dashboard_stats(
        self,
        db: Session,
    ) -> ServiceResult:

        stats = {
            "total_patients": self.dashboard_repository.get_total_patients(db),
            "total_doctors": self.dashboard_repository.get_total_doctors(db),
            "today_appointments": self.dashboard_repository.get_today_appointments(db),
            "scheduled": self.dashboard_repository.get_status_count(
                db,
                "Scheduled",
            ),
            "completed": self.dashboard_repository.get_status_count(
                db,
                "Completed",
            ),
            "cancelled": self.dashboard_repository.get_status_count(
                db,
                "Cancelled",
            ),
        }

        logger.info("Dashboard statistics retrieved.")

        return ServiceResult.Success(
            "Dashboard statistics retrieved successfully.",
            stats,
        )

    # -------------------------------------------------
    # Recent Patients
    # -------------------------------------------------

    def get_recent_patients(
        self,
        db: Session,
    ) -> ServiceResult:

        patients = self.dashboard_repository.get_recent_patients(
            db,
        )

        logger.info("Recent patients retrieved.")

        return ServiceResult.Success(
            "Recent patients retrieved successfully.",
            patients,
        )

    # -------------------------------------------------
    # Available Doctors
    # -------------------------------------------------

    def get_available_doctors(
        self,
        db: Session,
    ) -> ServiceResult:

        doctors = self.dashboard_repository.get_available_doctors(
            db,
        )

        logger.info("Available doctors retrieved.")

        return ServiceResult.Success(
            "Available doctors retrieved successfully.",
            doctors,
        )

    # -------------------------------------------------
    # Upcoming Appointments
    # -------------------------------------------------

    def get_upcoming_appointments(
        self,
        db: Session,
    ) -> ServiceResult:

        appointments = (
            self.dashboard_repository.get_upcoming_appointments(
                db,
            )
        )

        logger.info("Upcoming appointments retrieved.")

        return ServiceResult.Success(
            "Upcoming appointments retrieved successfully.",
            appointments,
        )