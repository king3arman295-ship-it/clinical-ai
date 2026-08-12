from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
)

from sqlalchemy.orm import relationship

from app.core.database import Base


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    prescription_id = Column(
        Integer,
        ForeignKey("prescriptions.id"),
        nullable=False,
    )

    medicine_name = Column(
        String(200),
        nullable=False,
    )

    form = Column(
        String(30),
        nullable=True,
    )

    dosage = Column(
        String(100),
        nullable=True,
    )

    frequency = Column(
        String(100),
        nullable=True,
    )

    duration = Column(
        String(100),
        nullable=True,
    )

    instructions = Column(
        Text,
        nullable=True,
    )

    # Units to dispense (tablets/bottles). Used by pharmacy stock decrement.
    quantity = Column(
        Integer,
        nullable=False,
        default=1,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    prescription = relationship(
        "Prescription",
        back_populates="items",
    )
