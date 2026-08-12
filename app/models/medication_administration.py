from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class MedicationAdministration(Base):
    """
    Medication Administration Record (MAR) — logs each individual dose
    given to an admitted (IPD) patient over the course of their stay.
    Distinct from the one-time OPD PharmacyOrder dispense: every logged
    dose here also decrements Medicine.stock_qty.
    """

    __tablename__ = "medication_administrations"

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

    medicine_id = Column(
        Integer,
        ForeignKey("medicines.id"),
        nullable=False,
    )

    scheduled_time = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    given_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Nurse/doctor/pharmacist who administered the dose.
    given_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    admission = relationship(
        "Admission",
        back_populates="medication_administrations",
    )

    medicine = relationship(
        "Medicine",
        back_populates="medication_administrations",
    )

    given_by_user = relationship(
        "User",
        foreign_keys=[given_by],
    )
