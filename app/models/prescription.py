from sqlalchemy import (
    Column,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # OPD prescription — written during a scheduled appointment.
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=True,
    )

    # IPD prescription — written during a ward round, tied to the
    # inpatient stay instead of a single appointment. Exactly one of
    # appointment_id / admission_id is set — see the check constraint
    # below. This is what lets the Pharmacist see medicines ordered for
    # admitted patients, not just OPD patients.
    admission_id = Column(
        Integer,
        ForeignKey("admissions.id"),
        nullable=True,
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
    )

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=False,
    )

    diagnosis = Column(
        Text,
        nullable=True,
    )

    advice = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    patient = relationship(
        "Patient",
        back_populates="prescriptions",
    )

    appointment = relationship(
        "Appointment",
        back_populates="prescriptions",
    )

    admission = relationship(
        "Admission",
        back_populates="prescriptions",
    )

    doctor = relationship(
        "Doctor",
    )

    items = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "appointment_id IS NOT NULL OR admission_id IS NOT NULL",
            name="ck_prescription_has_source",
        ),
    )
