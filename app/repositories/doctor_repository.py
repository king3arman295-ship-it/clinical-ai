from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.doctor import Doctor
from app.repositories.base_repository import BaseRepository


class DoctorRepository(BaseRepository[Doctor]):

    def __init__(self):
        super().__init__(Doctor)

    # -----------------------------------
    # Get All Doctors
    # -----------------------------------
    def get_all(
        self,
        db: Session,
    ):
        return (
            db.query(Doctor)
            .all()
        )

    # -----------------------------------
    # Get Doctor By ID
    # -----------------------------------
    def get_by_id(
        self,
        db: Session,
        doctor_id: int,
    ):
        return (
            db.query(Doctor)
            .filter(
                Doctor.id == doctor_id
            )
            .first()
        )

    # -----------------------------------
    # Get Available Doctor
    # -----------------------------------
    def get_available_doctor(
        self,
        db: Session,
        doctor_id: int,
    ):
        return (
            db.query(Doctor)
            .filter(
                Doctor.id == doctor_id,
                Doctor.available.is_(True),
            )
            .first()
        )

    # -----------------------------------
    # Get Doctor By Email
    # -----------------------------------
    def get_by_email(
        self,
        db: Session,
        email: str,
    ):
        return (
            db.query(Doctor)
            .filter(
                Doctor.email == email
            )
            .first()
        )

    # -----------------------------------
    # Get Doctor By Full Name
    # -----------------------------------
    def get_by_name(
    self,
    db: Session,
    name: str,
    ):
     return (
        db.query(Doctor)
        .filter(
            Doctor.full_name.ilike(f"%{name}%")
        )
        .first()
    )
    # -----------------------------------
    # Search Doctors By Name
    # -----------------------------------
    def search_by_name(
        self,
        db: Session,
        name: str,
    ):
        return (
            db.query(Doctor)
            .filter(
                Doctor.full_name.ilike(f"%{name}%")
            )
            .all()
        )

    # -----------------------------------
    # Get Doctors By Specialization
    # -----------------------------------
    def get_by_specialization(
        self,
        db: Session,
        specialization: str,
    ):
        return (
            db.query(Doctor)
            .filter(
                Doctor.specialization.ilike(
                    f"%{specialization}%"
                )
            )
            .all()
        )

    # -----------------------------------
    # Search By Name OR Specialization
    # -----------------------------------
    def search(
        self,
        db: Session,
        keyword: str,
    ):
        return (
            db.query(Doctor)
            .filter(
                or_(
                    Doctor.full_name.ilike(f"%{keyword}%"),
                    Doctor.specialization.ilike(f"%{keyword}%"),
                )
            )
            .all()
        )

    # -----------------------------------
    # Update Doctor
    # -----------------------------------
    def update(
        self,
        db: Session,
        doctor: Doctor,
    ):
        db.add(doctor)
        db.flush()
        db.refresh(doctor)
        return doctor

    # -----------------------------------
    # Delete Doctor
    # -----------------------------------
    def delete(
        self,
        db: Session,
        doctor: Doctor,
    ):
        db.delete(doctor)
        db.flush()
    def update_fcm_token(
    self,
    db,
    doctor_id: int,
    fcm_token: str,
   ):
      doctor = (
        db.query(self.model)
        .filter(self.model.id == doctor_id)
        .first()
    )

      if doctor:
        doctor.fcm_token = fcm_token
        db.flush()

      return doctor