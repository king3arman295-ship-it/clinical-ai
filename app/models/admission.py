from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import AdmissionStatus, AdmissionUrgency, ConditionFlag


class Admission(Base):
    __tablename__ = "admissions"

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

    # Doctor who raised the admission request (clinical decision).
    requesting_doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=False,
    )

    # Doctor attending the patient once admitted — usually the same as
    # requesting_doctor_id but kept separate in case of a handover.
    admitting_doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=True,
    )

    # Bed is only assigned once the Admission Head allocates one — the
    # doctor's request never picks a bed directly.
    bed_id = Column(
        Integer,
        ForeignKey("beds.id"),
        nullable=True,
    )

    reason = Column(
        Text,
        nullable=True,
    )

    diagnosis = Column(
        Text,
        nullable=True,
    )

    # routine / urgent / emergency — see app.common.enums.AdmissionUrgency
    urgency = Column(
        String(20),
        nullable=False,
        default=AdmissionUrgency.ROUTINE.value,
    )

    # general / icu / private / pediatric — preferred ward type requested
    # by the doctor; the Admission Head still picks the specific bed.
    preferred_ward_type = Column(
        String(20),
        nullable=True,
    )

    # pending / admitted / discharged / cancelled
    status = Column(
        String(20),
        nullable=False,
        default=AdmissionStatus.PENDING.value,
    )

    # stable / critical — set by the doctor, shown on the Admission Head's
    # bed-map dashboard.
    condition_flag = Column(
        String(20),
        nullable=True,
        default=ConditionFlag.STABLE.value,
    )

    discharge_summary = Column(
        Text,
        nullable=True,
    )

    requested_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    admitted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    discharged_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    patient = relationship(
        "Patient",
        back_populates="admissions",
    )

    requesting_doctor = relationship(
        "Doctor",
        foreign_keys=[requesting_doctor_id],
    )

    admitting_doctor = relationship(
        "Doctor",
        foreign_keys=[admitting_doctor_id],
    )

    bed = relationship(
        "Bed",
        back_populates="admissions",
    )

    notes = relationship(
        "AdmissionNote",
        back_populates="admission",
        cascade="all, delete-orphan",
    )

    medication_administrations = relationship(
        "MedicationAdministration",
        back_populates="admission",
        cascade="all, delete-orphan",
    )

    prescriptions = relationship(
        "Prescription",
        back_populates="admission",
        cascade="all, delete-orphan",
    )
