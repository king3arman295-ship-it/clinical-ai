from sqlalchemy.orm import Session

from app.common.service_result import ServiceResult

from app.core.logger import logger
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    ConflictException,
)

from app.models.patient import Patient

from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
)


class PatientService:

    def __init__(
        self,
        patient_repository,
    ):
        self.patient_repository = patient_repository

    # -----------------------------------
    # Create Patient
    # -----------------------------------
    def create_patient(
        self,
        db: Session,
        patient: PatientCreate,
    ) -> ServiceResult:

        existing_phone = self.patient_repository.get_by_phone(
            db,
            patient.phone,
        )

        if existing_phone:
            raise ConflictException(
                "A patient with this phone number already exists."
            )

        if patient.email:

            existing_email = self.patient_repository.get_by_email(
                db,
                patient.email,
            )

            if existing_email:
                raise ConflictException(
                    "A patient with this email already exists."
                )

        db_patient = Patient(
            name=patient.name,
            phone=patient.phone,
            email=patient.email,
        )

        with UnitOfWork(db):
            created = self.patient_repository.create(
                db,
                db_patient,
            )

        logger.info(
            f"Patient created | ID={created.id}"
        )

        return ServiceResult.Success(
            "Patient created successfully.",
            created,
        )
        # -----------------------------------
    # Find Or Create Patient
    # -----------------------------------
    def find_or_create_patient(
        self,
        db: Session,
        name: str,
        phone: str,
        email: str | None = None,
    ) -> Patient:

        # -----------------------------
        # Search By Phone
        # -----------------------------
        patient = self.patient_repository.get_by_phone(
            db,
            phone,
        )

        if patient:

            # Update name if changed
            if patient.name != name:
                patient.name = name

            # Update email if provided
            if (
                email
                and patient.email != email
            ):
                patient.email = email

            with UnitOfWork(db):
                patient = self.patient_repository.update(
                    db,
                    patient,
                )

            logger.info(
                f"Existing patient found | ID={patient.id}"
            )

            return patient

        # -----------------------------
        # Create New Patient
        # -----------------------------
        new_patient = Patient(
            name=name,
            phone=phone,
            email=email,
        )

        with UnitOfWork(db):
            new_patient = self.patient_repository.create(
                db,
                new_patient,
            )

        logger.info(
            f"New patient created | ID={new_patient.id}"
        )

        return new_patient
    # -----------------------------------
    # Get All Patients
    # -----------------------------------
    def get_all_patients(
        self,
        db: Session,
    ) -> ServiceResult:

        patients = self.patient_repository.get_all(db)

        return ServiceResult.Success(
            "Patients fetched successfully.",
            patients,
        )

    # -----------------------------------
    # Get Patient By ID
    # -----------------------------------
    def get_patient_by_id(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        patient = self.patient_repository.get_by_id(
            db,
            patient_id,
        )

        if not patient:
            raise NotFoundException(
                "Patient not found."
            )

        return ServiceResult.Success(
            "Patient fetched successfully.",
            patient,
        )
    def save_fcm_token(
    self,
    db,
    patient_id: int,
    fcm_token: str,
):

       with UnitOfWork(db):

        patient = self.patient_repository.update_fcm_token(
            db,
            patient_id,
            fcm_token,
        )

       return patient
    # -----------------------------------
    # Update Patient
    # -----------------------------------
    def update_patient(
        self,
        db: Session,
        patient_id: int,
        patient_data: PatientUpdate,
    ) -> ServiceResult:

        patient = self.patient_repository.get_by_id(
            db,
            patient_id,
        )

        if not patient:
            raise NotFoundException(
                "Patient not found."
            )

        update_data = patient_data.model_dump(
            exclude_unset=True,
        )

        if (
            "phone" in update_data
            and update_data["phone"] != patient.phone
        ):

            existing = self.patient_repository.get_by_phone(
                db,
                update_data["phone"],
            )

            if existing:
                raise ConflictException(
                    "Phone number already exists."
                )

        if (
            "email" in update_data
            and update_data["email"]
            and update_data["email"] != patient.email
        ):

            existing = self.patient_repository.get_by_email(
                db,
                update_data["email"],
            )

            if existing:
                raise ConflictException(
                    "Email already exists."
                )

        for key, value in update_data.items():
            setattr(patient, key, value)

        with UnitOfWork(db):
            updated = self.patient_repository.update(
                db,
                patient,
            )

        logger.info(
            f"Patient updated | ID={updated.id}"
        )

        return ServiceResult.Success(
            "Patient updated successfully.",
            updated,
        )

    # -----------------------------------
    # Delete Patient
    # -----------------------------------
    def delete_patient(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        patient = self.patient_repository.get_by_id(
            db,
            patient_id,
        )

        if not patient:
            raise NotFoundException(
                "Patient not found."
            )

        with UnitOfWork(db):
            self.patient_repository.delete(
                db,
                patient,
            )

        logger.info(
            f"Patient deleted | ID={patient_id}"
        )

        return ServiceResult.Success(
            "Patient deleted successfully.",
            {
                "message": "Patient deleted successfully."
            },
        )