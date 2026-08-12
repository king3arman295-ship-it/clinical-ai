from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import PharmacyOrderStatus


class PharmacyOrder(Base):
    """
    Fulfillment half of a prescription. One row per prescription item —
    created automatically when a doctor writes a prescription, then
    picked up and dispensed by the Pharmacist.
    """

    __tablename__ = "pharmacy_orders"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    prescription_item_id = Column(
        Integer,
        ForeignKey("prescription_items.id"),
        nullable=False,
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
    )

    # Nullable — the prescribed medicine name may not (yet) exist in the
    # inventory master list. Linked automatically by name where possible.
    medicine_id = Column(
        Integer,
        ForeignKey("medicines.id"),
        nullable=True,
    )

    # pending / dispensed / out_of_stock / cancelled
    status = Column(
        String(20),
        nullable=False,
        default=PharmacyOrderStatus.PENDING.value,
    )

    dispensed_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    dispensed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # How many units to deduct from inventory on dispense
    quantity = Column(
        Integer,
        nullable=False,
        default=1,
    )

    # Set when included on an issued (non-cancelled) bill
    bill_id = Column(
        Integer,
        ForeignKey("bills.id"),
        nullable=True,
    )

    # prescription | course (ward medication course)
    source = Column(
        String(30),
        nullable=False,
        default="prescription",
    )

    course_item_id = Column(
        Integer,
        ForeignKey("medication_course_items.id"),
        nullable=True,
    )

    # tablet / capsule / syrup / injection / drip / etc. (for inventory clarity)
    form = Column(
        String(30),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    prescription_item = relationship(
        "PrescriptionItem",
    )

    patient = relationship(
        "Patient",
        back_populates="pharmacy_orders",
    )

    medicine = relationship(
        "Medicine",
        back_populates="pharmacy_orders",
    )

    dispensed_by_user = relationship(
        "User",
        foreign_keys=[dispensed_by],
    )
