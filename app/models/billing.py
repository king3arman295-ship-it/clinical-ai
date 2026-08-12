from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Bill(Base):
    """
    Patient bill / receipt produced by the Billing Department.
    Aggregates consultation fees, medicines, lab tests, bed charges,
    and nursing service charges into a printable receipt.
    """

    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)

    bill_number = Column(String(40), nullable=False, unique=True, index=True)

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)

    # Optional episode of care — scopes the bill to one visit / stay
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    admission_id = Column(Integer, ForeignKey("admissions.id"), nullable=True)

    # Snapshot of patient identity at issue time (receipt stays readable later)
    patient_name = Column(String(150), nullable=False)
    patient_phone = Column(String(30), nullable=True)
    patient_email = Column(String(150), nullable=True)

    # draft | issued | paid | cancelled
    status = Column(String(20), nullable=False, default="issued")

    subtotal = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    total = Column(Float, nullable=False, default=0.0)

    currency = Column(String(10), nullable=False, default="PKR")

    notes = Column(Text, nullable=True)
    payment_method = Column(String(40), nullable=True)  # cash | card | transfer | insurance

    issued_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient = relationship("Patient", backref="bills")
    issuer = relationship("User", foreign_keys=[issued_by])
    items = relationship(
        "BillItem",
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillItem.id",
    )


class BillItem(Base):
    """One line on a bill — describes a service and its charge."""

    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)

    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)

    # consultation | medicine | lab | bed | nursing | other
    category = Column(String(30), nullable=False)

    description = Column(String(400), nullable=False)
    details = Column(Text, nullable=True)  # extra lines shown on receipt

    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)

    # Optional link back to source record
    reference_type = Column(String(40), nullable=True)  # appointment | pharmacy_order | lab_result | admission | dose
    reference_id = Column(Integer, nullable=True)

    bill = relationship("Bill", back_populates="items")
