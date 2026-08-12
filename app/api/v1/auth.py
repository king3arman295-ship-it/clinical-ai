from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.dependencies import get_db

from app.dependencies.services import get_auth_service

from app.auth.auth_service import AuthService
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.schemas.firebase import FCMTokenRequest
from app.auth.dependencies import get_current_user
from app.auth.roles import require_roles


class PatientRegisterRequest(BaseModel):
    name: str
    phone: str
    email: str
    username: str
    password: str

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
)
def register(
    user: UserCreate,
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
):

    result = service.register(
    db,
    user.username,
    user.email,
    user.password,
    user.role,
)

    return result.data


@router.get(
    "/staff",
    response_model=list[UserResponse],
)
def list_staff(
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
    current_user=Depends(require_roles("admin")),
):
    """Non-clinical staff accounts (Admission Head, Pharmacist, Receptionist,
    extra Admins) for the main Admin's Staff Accounts screen. Without this,
    the frontend had no way to load previously-created accounts and could
    only show the ones created in the current browser session, which
    disappeared on every refresh."""
    result = service.list_staff(db)
    return result.data


@router.post("/patient-register")
def patient_register(
    data: PatientRegisterRequest,
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
):
    result = service.register(db, data.username, data.email, data.password, "patient")
    if result.success:
        from app.models.patient import Patient
        from app.models.user import User
        from app.core.unit_of_work import UnitOfWork
        # Get the newly created user
        user = db.query(User).filter(User.username == data.username).first()
        if user:
            patient = Patient(name=data.name, phone=data.phone, email=data.email, user_id=user.id)
            with UnitOfWork(db):
                db.add(patient)
                db.flush()  # assigns patient.id before we reference it below
                user.patient_id = patient.id
                db.add(user)
    return {"message": "Patient account created successfully."}

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
):
    return service.login(
        db,
        form_data.username,
        form_data.password,
    )
@router.post("/fcm-token")
def save_fcm_token(
    request: FCMTokenRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
):

    result = service.save_fcm_token(
        db=db,
        username=current_user["username"],
        fcm_token=request.fcm_token,
        notify_login=request.notify_login,
    )

    return {
        "message": result.message,
    }