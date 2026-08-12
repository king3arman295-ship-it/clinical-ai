from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
)

from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    username = Column(
        String(100),
        unique=True,
        nullable=False,
    )

    email = Column(
        String(150),
        unique=True,
        nullable=False,
    )

    hashed_password = Column(
        String(255),
        nullable=False,
    )

    role = Column(
        String(30),
        default="admin",
    )
    fcm_token = Column(
        String,
        nullable=True,
    )

    # Foreign keys to patient/doctor records
    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=True,
        unique=True,
    )
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=True,
        unique=True,
    )

    # Relationships
    patient = relationship(
        "Patient",
        back_populates="user",
        foreign_keys="Patient.user_id",
    )
    doctor = relationship(
        "Doctor",
        back_populates="user",
        foreign_keys="Doctor.user_id",
    )