from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    Enum,
)

from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import Severity


class Diagnosis(Base):
    __tablename__ = "diagnoses"

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

    diagnosis = Column(
        String(300),
        nullable=False,
    )

    severity = Column(
        Enum(
            Severity,
            values_callable=lambda enum: [e.value for e in enum],
            name="severity_enum",
        ),
        nullable=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    patient = relationship(
        "Patient",
        back_populates="diagnoses",
    )

    appointment = relationship(
        "Appointment",
        back_populates="diagnoses",
    )
