from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class WalkInSale(Base):
    """OTC / counter sale — patient walks up without a doctor order."""

    __tablename__ = "pharmacy_walk_in_sales"

    id = Column(Integer, primary_key=True, index=True)

    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    # Optional: registered patient, or free-text counter customer
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    unit_price = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False, default=0.0)

    sold_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    medicine = relationship("Medicine")
