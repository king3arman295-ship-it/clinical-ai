from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class ServicePricing(Base):
    """Hospital-wide fee schedule managed by main admin.

    One row per fee key (e.g. nursing_per_dose, nursing_per_day,
    hospital_service_fee, default_consultation_fee).
    """

    __tablename__ = "service_pricing"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(80), unique=True, nullable=False, index=True)
    label = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
