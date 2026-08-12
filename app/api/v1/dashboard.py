from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.services.dashboard_service import DashboardService
from app.dependencies.services import get_dashboard_service

from app.auth.roles import require_roles


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/public-stats")
def public_stats(
    db: Session = Depends(get_db),
    service: DashboardService = Depends(get_dashboard_service),
):
    return {
        "doctors": service.dashboard_repository.get_total_doctors(db),
        "patients": service.dashboard_repository.get_total_patients(db),
    }


# -------------------------------------------------
# Dashboard Statistics
# Admin, Receptionist, Doctor
# -------------------------------------------------

@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    service: DashboardService = Depends(get_dashboard_service),
    current_user=Depends(
        require_roles(
            "admin",
            "receptionist",
            "doctor",
        )
    ),
):
    result = service.get_dashboard_stats(db)

    return result.data


# -------------------------------------------------
# Recent Patients
# Admin, Receptionist
# -------------------------------------------------

@router.get("/recent-patients")
def recent_patients(
    db: Session = Depends(get_db),
    service: DashboardService = Depends(get_dashboard_service),
    current_user=Depends(
        require_roles(
            "admin",
            "receptionist",
        )
    ),
):
    result = service.get_recent_patients(db)

    return result.data


# -------------------------------------------------
# Available Doctors
# Admin, Receptionist, Doctor
# -------------------------------------------------

@router.get("/available-doctors")
def available_doctors(
    db: Session = Depends(get_db),
    service: DashboardService = Depends(get_dashboard_service),
    current_user=Depends(
        require_roles(
            "admin",
            "receptionist",
            "doctor",
        )
    ),
):
    result = service.get_available_doctors(db)

    return result.data


# -------------------------------------------------
# Upcoming Appointments
# Admin, Receptionist, Doctor
# -------------------------------------------------

@router.get("/upcoming")
def upcoming_appointments(
    db: Session = Depends(get_db),
    service: DashboardService = Depends(get_dashboard_service),
    current_user=Depends(
        require_roles(
            "admin",
            "receptionist",
            "doctor",
        )
    ),
):
    result = service.get_upcoming_appointments(db)

    return result.data