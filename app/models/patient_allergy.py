from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
)

from sqlalchemy.orm import relationship

from app.core.database import Base


class PatientAllergy(Base):
    __tablename__ = "patient_allergies"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
    )

    allergy_name = Column(
        String(200),
        nullable=False,
    )

    reaction = Column(
        String(300),
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
        back_populates="allergies",
    )
