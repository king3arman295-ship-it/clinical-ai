from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Time,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.common.enums import (
    AppointmentType,
    AppointmentStatus,
    MeetingStatus,
)


class Appointment(Base):
    __tablename__ = "appointments"

    # ---------------------------------------------------------
    # Primary Key
    # ---------------------------------------------------------
    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ---------------------------------------------------------
    # Foreign Keys
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # Appointment Details
    # ---------------------------------------------------------
    appointment_date = Column(
        Date,
        nullable=False,
    )

    appointment_time = Column(
        Time,
        nullable=False,
    )

    status = Column(
        Enum(
            AppointmentStatus,
            values_callable=lambda enum: [e.value for e in enum],
            name="appointment_status_enum",
        ),
        nullable=False,
        default=AppointmentStatus.SCHEDULED,
    )

    appointment_type = Column(
        Enum(
            AppointmentType,
            values_callable=lambda enum: [e.value for e in enum],
            name="appointment_type_enum",
        ),
        nullable=False,
        default=AppointmentType.PHYSICAL,
    )

    reason = Column(
        String(300),
        nullable=True,
    )

    notes = Column(
        String(500),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Video Consultation
    # ---------------------------------------------------------
    video_channel = Column(
        String(150),
        nullable=True,
    )

    meeting_status = Column(
        Enum(
            MeetingStatus,
            values_callable=lambda enum: [e.value for e in enum],
            name="meeting_status_enum",
        ),
        nullable=False,
        default=MeetingStatus.SCHEDULED,
    )

    meeting_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    meeting_ended_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    call_duration = Column(
        Integer,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Notification
    # ---------------------------------------------------------
    notification_sent = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Audit Fields
    # ---------------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    patient = relationship(
        "Patient",
        back_populates="appointments",
    )

    doctor = relationship(
        "Doctor",
    )

    reports = relationship(
        "PatientReport",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

    prescriptions = relationship(
        "Prescription",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

    diagnoses = relationship(
        "Diagnosis",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

    vitals = relationship(
        "PatientVital",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

    doctor_notes = relationship(
        "DoctorNote",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )