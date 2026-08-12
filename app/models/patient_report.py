from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import ReportType


class PatientReport(Base):
    __tablename__ = "patient_reports"

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

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=True,
    )

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=True,
    )

    report_name = Column(
        String(200),
        nullable=False,
    )

    report_type = Column(
        Enum(
            ReportType,
            values_callable=lambda enum: [e.value for e in enum],
            name="report_type_enum",
        ),
        nullable=False,
        default=ReportType.OTHER,
    )

    file_path = Column(
        String(500),
        nullable=False,
    )

    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    patient = relationship(
        "Patient",
        back_populates="reports",
    )

    appointment = relationship(
        "Appointment",
        back_populates="reports",
    )

    doctor = relationship("Doctor")
