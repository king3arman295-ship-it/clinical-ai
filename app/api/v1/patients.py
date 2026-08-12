from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
)

from app.services.patient_service import PatientService
from app.dependencies.services import get_patient_service

from app.auth.roles import require_roles
from pydantic import BaseModel


class FCMTokenRequest(BaseModel):
    fcm_token: str


router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
)


@router.post("/", response_model=PatientResponse)
def create_patient(
    patient: PatientCreate,
    db: Session = Depends(get_db),
    service: PatientService = Depends(get_patient_service),
    current_user=Depends(require_roles("admin", "receptionist")),
):
    result = service.create_patient(
        db,
        patient,
    )

    return result.data


@router.get("/", response_model=list[PatientResponse])
def get_all_patients(
    db: Session = Depends(get_db),
    service: PatientService = Depends(get_patient_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor", "admission_head", "pharmacist", "lab_technician")),
):
    result = service.get_all_patients(db)

    return result.data


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    service: PatientService = Depends(get_patient_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor", "admission_head", "pharmacist", "lab_technician")),
):
    result = service.get_patient_by_id(
        db,
        patient_id,
    )

    return result.data


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    patient: PatientUpdate,
    db: Session = Depends(get_db),
    service: PatientService = Depends(get_patient_service),
    current_user=Depends(require_roles("admin", "receptionist")),
):
    result = service.update_patient(
        db,
        patient_id,
        patient,
    )

    return result.data


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    service: PatientService = Depends(get_patient_service),
    current_user=Depends(require_roles("admin")),
):
    result = service.delete_patient(
        db,
        patient_id,
    )

    return result.data


# ---------------------------------------------------------
# Save Patient FCM Token
# ---------------------------------------------------------
@router.post("/{patient_id}/fcm-token")
def save_patient_fcm_token(
    patient_id: int,
    request: FCMTokenRequest,
    db: Session = Depends(get_db),
    service: PatientService = Depends(get_patient_service),
):
    service.save_fcm_token(
        db,
        patient_id,
        request.fcm_token,
    )

    return {
        "message": "Patient FCM token saved successfully."
    }