from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class LabResult(Base):
    """Individual test result belonging to a LabOrder."""

    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, index=True)

    lab_order_id = Column(Integer, ForeignKey("lab_orders.id"), nullable=False)
    lab_test_id = Column(Integer, ForeignKey("lab_tests.id"), nullable=False)

    # Result value — support both numeric and textual results
    value_numeric = Column(Float, nullable=True)
    value_text = Column(String(500), nullable=True)
    unit = Column(String(50), nullable=True)

    is_abnormal = Column(Boolean, nullable=False, default=False)
    remarks = Column(Text, nullable=True)

    # pending / entered / verified
    status = Column(String(20), nullable=False, default="pending")

    entered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    entered_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lab_order = relationship("LabOrder", back_populates="results")
    lab_test = relationship("LabTest", back_populates="results")
    entered_by_user = relationship("User", foreign_keys=[entered_by])
    verified_by_user = relationship("User", foreign_keys=[verified_by])
