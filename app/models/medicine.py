from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import MedicineForm


class Medicine(Base):
    """Pharmacy inventory master list — one row per stocked medicine."""

    __tablename__ = "medicines"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
        unique=False,
        index=True,
    )

    # tablet / capsule / syrup / injection / ointment / drops / other
    form = Column(
        String(20),
        nullable=False,
        default=MedicineForm.TABLET.value,
    )

    dosage = Column(
        String(100),
        nullable=True,
    )

    unit = Column(
        String(30),
        nullable=False,
        default="units",
    )

    stock_qty = Column(
        Integer,
        nullable=False,
        default=0,
    )

    reorder_threshold = Column(
        Integer,
        nullable=False,
        default=10,
    )

    # Selling price used by Billing Department
    unit_price = Column(
        Float,
        nullable=False,
        default=50.0,
    )

    batch_number = Column(
        String(100),
        nullable=True,
    )

    expiry_date = Column(
        Date,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    pharmacy_orders = relationship(
        "PharmacyOrder",
        back_populates="medicine",
    )

    medication_administrations = relationship(
        "MedicationAdministration",
        back_populates="medicine",
    )
