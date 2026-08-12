from sqlalchemy.orm import Session

from app.models.user import User

from app.auth.security import (
    hash_password,
    verify_password
)

from app.auth.jwt import create_access_token

from app.common.service_result import ServiceResult
from app.common.messages import Messages

from app.core.unit_of_work import UnitOfWork
from app.core.logger import logger

from app.exceptions.exceptions import (
    ConflictException,
    UnauthorizedException
)


class AuthService:

    def __init__(self, user_repository):
        self.user_repository = user_repository

    def register(
      self,
      db,
      username,
      email,
      password,
      role,
     ):

        if self.user_repository.get_by_username(
            db,
            username,
        ):
            raise ConflictException(
                "Username already exists."
            )

        if self.user_repository.get_by_email(
            db,
            email,
        ):
            raise ConflictException(
                "Email already exists."
            )

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=role,
        )

        with UnitOfWork(db):
            user = self.user_repository.create(
                db,
                user,
            )

        return ServiceResult.Success(
            "User registered successfully.",
            user,
        )

    # Non-clinical staff accounts created by the admin from the Staff
    # Accounts screen (admission_head, pharmacist, receptionist, extra
    # admins). "patient" and "doctor" logins are excluded here since those
    # are managed from their own dedicated screens, not the staff list.
    STAFF_ROLES = ("admission_head", "pharmacist", "lab_technician", "nurse", "billing", "receptionist", "admin")

    def list_staff(self, db: Session):
        staff = [
            user
            for user in self.user_repository.get_all(db)
            if user.role in self.STAFF_ROLES
        ]
        staff.sort(key=lambda u: u.id, reverse=True)
        return ServiceResult.Success(Messages.SUCCESS, staff)


    def login(
        self,
        db: Session,
        username: str,
        password: str,
    ):
        user = self.user_repository.get_by_username(
            db,
            username,
        )

        if (
            not user
            or not verify_password(
                password,
                user.hashed_password,
            )
        ):
            raise UnauthorizedException(
                "Invalid username or password."
            )

        doctor_id = user.doctor_id
        patient_id = user.patient_id

        token = create_access_token(
            {
                "sub": user.username,
                "id": user.id,
                "role": user.role,
                "doctor_id": doctor_id,
                "patient_id": patient_id,
            }
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
        }
    def save_fcm_token(
        self,
        db: Session,
        username: str,
        fcm_token: str,
        notify_login: bool = False,
    ):

        user = self.user_repository.get_by_username(
            db,
            username,
        )

        if not user:
            raise UnauthorizedException(
                "User not found."
            )

        with UnitOfWork(db):
            self.user_repository.update_fcm_token(
                db,
                user,
                fcm_token,
            )

        # Also save the FCM token on the Patient/Doctor record itself, since
        # that's what appointment_service.notify_incoming_call() (and the
        # reminder scheduler) actually reads.
        #
        # Deliberately NOT using the `user.patient` / `user.doctor`
        # relationships here — those join through Patient.user_id /
        # Doctor.user_id, a *separate* back-reference column from
        # user.patient_id / user.doctor_id (the ones login/JWT/every other
        # lookup in this codebase actually relies on). If that back-reference
        # was ever left NULL — e.g. a patient record created any way other
        # than the one exact /auth/patient-register path that sets both
        # sides — the relationship silently resolves to None and no error
        # is raised. Querying by user.patient_id / user.doctor_id directly
        # sidesteps that mismatch entirely.
        try:
            if user.role == "patient" and user.patient_id:
                from app.models.patient import Patient
                patient = db.query(Patient).filter(Patient.id == user.patient_id).first()
                if patient:
                    patient.fcm_token = fcm_token
                    with UnitOfWork(db):
                        db.add(patient)
                else:
                    logger.warning(
                        f"save_fcm_token: user '{username}' has patient_id="
                        f"{user.patient_id} but no matching Patient row exists."
                    )
            elif user.role == "doctor" and user.doctor_id:
                from app.models.doctor import Doctor
                doctor = db.query(Doctor).filter(Doctor.id == user.doctor_id).first()
                if doctor:
                    doctor.fcm_token = fcm_token
                    with UnitOfWork(db):
                        db.add(doctor)
                else:
                    logger.warning(
                        f"save_fcm_token: user '{username}' has doctor_id="
                        f"{user.doctor_id} but no matching Doctor row exists."
                    )
        except Exception as e:
            logger.error(f"save_fcm_token: failed to sync token to Patient/Doctor record: {e}")

        # Trigger login notification — only for an actual fresh login.
        # This same save_fcm_token path is also hit on every ordinary page
        # load/refresh (the frontend keeps the token fresh for the video
        # reminder scheduler), and those calls pass notify_login=False so
        # they don't re-fire the "welcome back" push every time.
        if notify_login:
            try:
                from app.services.firebase_service import send_notification
                send_notification(
                    token=fcm_token,
                    title="Welcome to Lumina Health",
                    body=f"Hello {username}, you have successfully logged in!",
                )
            except Exception as e:
                from app.core.logger import logger
                logger.error(f"Failed to send FCM notification: {e}")

        return ServiceResult.Success(
            "FCM token saved successfully.",
            None,
        )
