from sqlalchemy import (
    Column,
    Integer,
    Text,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class DoctorNote(Base):
    __tablename__ = "doctor_notes"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=False,
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

    note = Column(
        Text,
        nullable=False,
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
        back_populates="doctor_notes",
    )

    appointment = relationship(
        "Appointment",
        back_populates="doctor_notes",
    )

    doctor = relationship(
        "Doctor",
    )
