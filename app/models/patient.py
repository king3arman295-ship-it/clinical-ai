from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func

from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import PatientCareType


class Patient(Base):
    __tablename__ = "patients"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(100),
        nullable=False,
    )

    phone = Column(
        String(20),
        unique=True,
        nullable=False,
    )

    email = Column(
        String(100),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    fcm_token = Column(
        String,
        nullable=True,
    )

    # OPD (outpatient) vs IPD (currently admitted). Flipped by
    # AdmissionService when a bed is allocated / patient discharged.
    care_type = Column(
        String(10),
        nullable=False,
        default=PatientCareType.OPD.value,
        server_default=PatientCareType.OPD.value,
    )

    # Foreign key to User
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        unique=True,
    )

    # Relationship to User
    user = relationship(
        "User",
        back_populates="patient",
        foreign_keys="Patient.user_id",
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    appointments = relationship(
        "Appointment",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    medical_history = relationship(
        "MedicalHistory",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    reports = relationship(
        "PatientReport",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    prescriptions = relationship(
        "Prescription",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    doctor_notes = relationship(
        "DoctorNote",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    vitals = relationship(
        "PatientVital",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    allergies = relationship(
        "PatientAllergy",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    diagnoses = relationship(
        "Diagnosis",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    admissions = relationship(
        "Admission",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    lab_orders = relationship(
        "LabOrder",
        back_populates="patient",
    )

    pharmacy_orders = relationship(
        "PharmacyOrder",
        back_populates="patient",
        cascade="all, delete-orphan",
    )