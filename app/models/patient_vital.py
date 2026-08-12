from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class PatientVital(Base):
    __tablename__ = "patient_vitals"

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

    height = Column(
        Float,
        nullable=True,
    )

    weight = Column(
        Float,
        nullable=True,
    )

    temperature = Column(
        Float,
        nullable=True,
    )

    blood_pressure = Column(
        String(20),
        nullable=True,
    )

    pulse = Column(
        Integer,
        nullable=True,
    )

    oxygen_level = Column(
        Float,
        nullable=True,
    )

    recorded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    patient = relationship(
        "Patient",
        back_populates="vitals",
    )

    appointment = relationship(
        "Appointment",
        back_populates="vitals",
    )
