from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.dependencies.services import get_appointment_service
from app.services.appointment_service import AppointmentService

from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
)

from app.auth.roles import require_roles
from fastapi import APIRouter, Depends, status
from app.schemas.appointment import FCMTokenRequest


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)

# -------------------------------------------------
# Patient Self-Book Appointment
# -------------------------------------------------

from app.auth.dependencies import get_current_user

@router.post("/my", response_model=AppointmentResponse)
def book_my_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(get_current_user),
):
    patient_id = current_user.get("patient_id")
    if not patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")
    
    # Override patient_id to ensure they book for themselves
    appointment.patient_id = patient_id
    
    result = service.book_appointment(
        db,
        appointment,
    )

    return result.data


# -------------------------------------------------
# Get My Appointments (Patient)
# -------------------------------------------------

@router.get("/my", response_model=list[AppointmentResponse])
def get_my_appointments(
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(get_current_user),
):
    patient_id = current_user.get("patient_id")
    if not patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")
    result = service.get_my_appointments(db, patient_id)
    return result.data


# -------------------------------------------------
# Cancel My Appointment (Patient)
# -------------------------------------------------

@router.put("/my/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_my_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(get_current_user),
):
    """
    Lets a logged-in patient cancel their own appointment.
    Ownership + status (can't cancel completed/already-cancelled
    appointments) are enforced in the service layer.
    """
    patient_id = current_user.get("patient_id")
    if not patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")

    result = service.cancel_appointment(
        db,
        appointment_id,
        patient_id,
    )

    return result.data

# -------------------------------------------------
# Update Appointment Status (Doctor)
# -------------------------------------------------

@router.put("/{appointment_id}/status", response_model=AppointmentResponse)
def update_appointment_status(
    appointment_id: int,
    appointment: AppointmentUpdate,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(get_current_user),
):
    doctor_id = current_user.get("doctor_id")
    if not doctor_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Doctor access required.")
    
    # Verify this doctor owns this appointment
    appointment_obj = service.get_appointment_by_id(db, appointment_id)
    if not appointment_obj or not appointment_obj.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment_obj.data.doctor_id != doctor_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")
    
    result = service.update_appointment(
        db,
        appointment_id,
        appointment,
    )

    return result.data


# -------------------------------------------------
# Update Appointment
# Admin & Receptionist
# -------------------------------------------------

@router.post("/", response_model=AppointmentResponse)
def book_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(require_roles("admin", "receptionist")),
):
    result = service.book_appointment(
        db,
        appointment,
    )

    return result.data


# -------------------------------------------------
# Patient Self-Book Appointment
# -------------------------------------------------

@router.post("/patient", response_model=AppointmentResponse)
def book_patient_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(get_current_user),
):
    patient_id = current_user.get("patient_id")
    if not patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")
    
    # Ensure the appointment is for the current patient
    appointment.patient_id = patient_id
    
    result = service.book_appointment(
        db,
        appointment,
    )

    return result.data


# -------------------------------------------------
# Get All Appointments
# Admin, Receptionist & Doctor
# -------------------------------------------------

@router.get("/", response_model=list[AppointmentResponse])
def get_all_appointments(
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor", "lab_technician", "pharmacist", "admission_head")),
):
    result = service.get_all_appointments(db)

    return result.data


# -------------------------------------------------
# Get Appointment By ID
# Admin, Receptionist & Doctor
# -------------------------------------------------

@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):
    result = service.get_appointment_by_id(
        db,
        appointment_id,
    )

    return result.data


# -------------------------------------------------
# Update Appointment
# Admin, Receptionist & Doctor
# -------------------------------------------------

@router.put("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: int,
    appointment: AppointmentUpdate,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(require_roles("admin", "receptionist", "doctor")),
):
    result = service.update_appointment(
        db,
        appointment_id,
        appointment,
    )

    return result.data

# ---------------------------------------------------------
# Join Video Meeting (Patient or Doctor)
# ---------------------------------------------------------

from app.auth.dependencies import get_current_user

@router.post(
    "/{appointment_id}/join",
    status_code=status.HTTP_200_OK,
)
def join_video_meeting(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(get_current_user),
):
    """
    Join a video consultation. Validates user owns this appointment.
    """
    # Verify ownership
    user_role = current_user.get("role")
    user_id = current_user.get("patient_id") if user_role == "patient" else current_user.get("doctor_id")
    
    appointment = service.get_appointment_by_id(db, appointment_id)
    if not appointment or not appointment.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appt = appointment.data
    
    if user_role == "patient" and appt.patient_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")
    elif user_role == "doctor" and appt.doctor_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")
    elif user_role not in ("patient", "doctor"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Only patient or doctor can join")
    
    result = service.join_video_meeting(
        db=db,
        appointment_id=appointment_id,
    )

    if hasattr(result, 'to_response'):
        return result.to_response()

    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
    }

@router.post(
    "/{appointment_id}/end",
)
def end_video_meeting(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(
        get_appointment_service,
    ),
    current_user=Depends(get_current_user),
):

    # Verify ownership
    user_role = current_user.get("role")
    user_id = current_user.get("patient_id") if user_role == "patient" else current_user.get("doctor_id")
    
    appointment = service.get_appointment_by_id(db, appointment_id)
    if not appointment or not appointment.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appt = appointment.data
    
    if user_role == "patient" and appt.patient_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")
    elif user_role == "doctor" and appt.doctor_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")
    elif user_role not in ("patient", "doctor"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Only patient or doctor can end")

    result = service.end_video_meeting(
        db,
        appointment_id,
    )

    return result
# -------------------------------------------------
# Delete Appointment
# Admin Only
# -------------------------------------------------

@router.delete("/{appointment_id}")
def delete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(require_roles("admin")),
):
    result = service.delete_appointment(
        db,
        appointment_id,
    )

    return {
        "message": result.message
    }
# ---------------------------------------------------------
# Get Video Meeting Details
# ---------------------------------------------------------

@router.get(
    "/{appointment_id}/video-details",
    summary="Get Video Meeting Details",
)
def get_video_details(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
):
    result = service.get_video_details(
        db,
        appointment_id,
    )

    return result.to_response()
# -------------------------------------------------
# Doctor Join Video Meeting
# -------------------------------------------------

@router.post("/{appointment_id}/join/patient")
def join_patient_video_meeting(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = current_user.get("patient_id")
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")
    
    service = get_appointment_service()
    
    # Verify ownership
    appointment = service.get_appointment_by_id(db, appointment_id)
    if not appointment or not appointment.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.data.patient_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")

    result = service.join_patient_meeting(
        db,
        appointment_id,
    )

    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
    }

@router.post("/{appointment_id}/join/doctor")
def join_doctor_video_meeting(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = current_user.get("doctor_id")
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Doctor access required.")
    
    service = get_appointment_service()
    
    # Verify ownership
    appointment = service.get_appointment_by_id(db, appointment_id)
    if not appointment or not appointment.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.data.doctor_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")

    result = service.join_doctor_meeting(
        db=db,
        appointment_id=appointment_id,
    )

    return {
    "success": result.success,
    "message": result.message,
    "data": result.data,
    }
@router.post("/{appointment_id}/notify-patient-call")
def notify_patient_call(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
    current_user=Depends(get_current_user),
):
    """
    Doctor-only. Fired right after the doctor starts a video call — pushes
    a call-style browser notification (Accept/Decline) to the patient's
    device so they can join. The patient has no way to start a call
    themselves; this is the only entry point into the meeting for them.
    """
    doctor_id = current_user.get("doctor_id")
    if not doctor_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Doctor access required.")

    appointment = service.get_appointment_by_id(db, appointment_id)
    if not appointment or not appointment.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.data.doctor_id != doctor_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not your appointment")

    result = service.notify_incoming_call(db, appointment_id)

    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
    }


@router.post("/{appointment_id}/register-patient-token")
def register_patient_token(
    appointment_id: int,
    request: FCMTokenRequest,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
):
    result = service.save_patient_fcm_token(
        db,
        appointment_id,
        request.fcm_token,
    )

    return result
@router.post("/{appointment_id}/register-doctor-token")
def register_doctor_token(
    appointment_id: int,
    request: FCMTokenRequest,
    db: Session = Depends(get_db),
    service: AppointmentService = Depends(get_appointment_service),
):
    result = service.save_doctor_fcm_token(
        db,
        appointment_id,
        request.fcm_token,
    )

    return result