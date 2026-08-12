from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.doctor import (
    DoctorCreate,
    DoctorUpdate,
    DoctorResponse,
    DoctorAvailabilityUpdate,
)

from app.services.doctor_service import DoctorService
from app.dependencies.services import get_doctor_service

from app.auth.roles import require_roles
from app.auth.dependencies import get_current_user
from fastapi import HTTPException
from pydantic import BaseModel


class FCMTokenRequest(BaseModel):
    fcm_token: str


router = APIRouter(
    prefix="/doctors",
    tags=["Doctors"],
)


@router.post("/", response_model=DoctorResponse)
def create_doctor(
    doctor: DoctorCreate,
    db: Session = Depends(get_db),
    service: DoctorService = Depends(get_doctor_service),
    current_user=Depends(require_roles("admin")),
):
    result = service.create_doctor(
        db,
        doctor,
    )

    return result.data


@router.get("/", response_model=list[DoctorResponse])
def get_all_doctors(
    db: Session = Depends(get_db),
    service: DoctorService = Depends(get_doctor_service),
):
    result = service.get_all_doctors(db)

    return result.data


@router.patch("/me/availability", response_model=DoctorResponse)
def update_my_availability(
    payload: DoctorAvailabilityUpdate,
    db: Session = Depends(get_db),
    service: DoctorService = Depends(get_doctor_service),
    current_user=Depends(require_roles("doctor")),
):
    doctor_id = current_user.get("doctor_id")
    if not doctor_id:
        raise HTTPException(status_code=403, detail="Doctor profile not found for this account.")

    result = service.update_doctor(
        db,
        doctor_id,
        DoctorUpdate(available=payload.available),
    )

    return result.data


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    service: DoctorService = Depends(get_doctor_service),
):
    result = service.get_doctor_by_id(
        db,
        doctor_id,
    )

    return result.data


@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    doctor: DoctorUpdate,
    db: Session = Depends(get_db),
    service: DoctorService = Depends(get_doctor_service),
    current_user=Depends(require_roles("admin")),
):
    result = service.update_doctor(
        db,
        doctor_id,
        doctor,
    )

    return result.data


@router.delete("/{doctor_id}")
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    service: DoctorService = Depends(get_doctor_service),
    current_user=Depends(require_roles("admin")),
):
    result = service.delete_doctor(
        db,
        doctor_id,
    )

    return result.data
@router.post("/{doctor_id}/fcm-token")
def save_doctor_fcm_token(
    doctor_id: int,
    request: FCMTokenRequest,
    db: Session = Depends(get_db),
    service: DoctorService = Depends(get_doctor_service),
):
    service.save_fcm_token(
        db,
        doctor_id,
        request.fcm_token,
    )

    return {
        "message": "Doctor FCM token saved successfully."
    }