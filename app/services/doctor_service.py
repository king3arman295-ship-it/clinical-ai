from sqlalchemy.orm import Session

from app.common.service_result import ServiceResult

from app.core.logger import logger
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    ConflictException,
)

from app.models.doctor import Doctor
from app.models.user import User
from app.auth.security import hash_password

from app.schemas.doctor import (
    DoctorCreate,
    DoctorUpdate,
)


class DoctorService:

    def __init__(self, doctor_repository, user_repository):
        self.doctor_repository = doctor_repository
        self.user_repository = user_repository

    # -----------------------------------
    # Create Doctor
    # -----------------------------------
    def create_doctor(
        self,
        db: Session,
        doctor: DoctorCreate,
    ) -> ServiceResult:

        existing = self.doctor_repository.get_by_email(db, doctor.email)
        if existing:
            raise ConflictException("Doctor with this email already exists.")

        if self.user_repository.get_by_username(db, doctor.username):
            raise ConflictException("Username already exists.")

        if self.user_repository.get_by_email(db, doctor.email):
            raise ConflictException("An account with this email already exists.")

        db_doctor = Doctor(
            full_name=doctor.full_name,
            specialization=doctor.specialization,
            qualification=doctor.qualification,
            phone=doctor.phone,
            email=doctor.email,
            consultation_fee=doctor.consultation_fee,
            experience_years=doctor.experience_years,
            available=doctor.available,
        )

        with UnitOfWork(db):
            created = self.doctor_repository.create(
                db,
                db_doctor,
            )
            user = self.user_repository.create(
                db,
                User(
                    username=doctor.username,
                    email=doctor.email,
                    hashed_password=hash_password(doctor.password),
                    role="doctor",
                ),
            )
            user.doctor_id = created.id

        logger.info(
            f"Doctor created | ID={created.id} | Name={created.full_name}"
        )

        return ServiceResult.Success(
            "Doctor and login account created successfully.",
            created,
        )

    # -----------------------------------
    # Get All Doctors
    # -----------------------------------
    def get_all_doctors(
        self,
        db: Session,
    ) -> ServiceResult:

        doctors = self.doctor_repository.get_all(db)

        return ServiceResult.Success(
            "Doctors fetched successfully.",
            doctors,
        )

    # -----------------------------------
    # Get Doctor By ID
    # -----------------------------------
    def get_doctor_by_id(
        self,
        db: Session,
        doctor_id: int,
    ) -> ServiceResult:

        doctor = self.doctor_repository.get_by_id(
            db,
            doctor_id,
        )

        if not doctor:
            raise NotFoundException(
                "Doctor not found."
            )

        return ServiceResult.Success(
            "Doctor fetched successfully.",
            doctor,
        )
    def save_fcm_token(
    self,
    db,
    doctor_id: int,
    fcm_token: str,
):

       with UnitOfWork(db):

        doctor = self.doctor_repository.update_fcm_token(
            db,
            doctor_id,
            fcm_token,
        )

       return doctor
    # -----------------------------------
    # Update Doctor
    # -----------------------------------
    def update_doctor(
        self,
        db: Session,
        doctor_id: int,
        doctor_data: DoctorUpdate,
    ) -> ServiceResult:

        doctor = self.doctor_repository.get_by_id(
            db,
            doctor_id,
        )

        if not doctor:
            raise NotFoundException(
                "Doctor not found."
            )

        update_data = doctor_data.model_dump(
            exclude_unset=True
        )

        for key, value in update_data.items():
            setattr(doctor, key, value)

        with UnitOfWork(db):
            updated = self.doctor_repository.update(
                db,
                doctor,
            )

        logger.info(
            f"Doctor updated | ID={updated.id}"
        )

        return ServiceResult.Success(
            "Doctor updated successfully.",
            updated,
        )

    # -----------------------------------
    # Delete Doctor
    # -----------------------------------
    def delete_doctor(
        self,
        db: Session,
        doctor_id: int,
    ) -> ServiceResult:

        doctor = self.doctor_repository.get_by_id(
            db,
            doctor_id,
        )

        if not doctor:
            raise NotFoundException(
                "Doctor not found."
            )

        with UnitOfWork(db):
            self.doctor_repository.delete(
                db,
                doctor,
            )

        logger.info(
            f"Doctor deleted | ID={doctor_id}"
        )

        return ServiceResult.Success(
            "Doctor deleted successfully.",
            {
                "message": "Doctor deleted successfully."
            },
        )
