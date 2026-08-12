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


class AdmissionNote(Base):
    """
    Rounds / progress notes logged against an inpatient stay. Kept
    distinct from OPD appointment notes (DoctorNote) since an admission
    isn't tied to a single appointment.
    """

    __tablename__ = "admission_notes"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    admission_id = Column(
        Integer,
        ForeignKey("admissions.id"),
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

    vitals = Column(
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
    admission = relationship(
        "Admission",
        back_populates="notes",
    )

    doctor = relationship(
        "Doctor",
    )
