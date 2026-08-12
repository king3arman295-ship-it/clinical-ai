from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    Boolean,
    DateTime,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import LabSampleType, LabTestCategory


class LabTest(Base):
    """Master catalog of laboratory tests the clinic offers."""

    __tablename__ = "lab_tests"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(200), nullable=False, unique=True)
    code = Column(String(50), nullable=True, unique=True)  # e.g. CBC, LFT, HbA1c
    category = Column(
        String(30),
        nullable=False,
        default=LabTestCategory.OTHER.value,
    )
    sample_type = Column(
        String(20),
        nullable=False,
        default=LabSampleType.BLOOD.value,
    )
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)  # e.g. g/dL, mg/dL
    normal_range_min = Column(Float, nullable=True)
    normal_range_max = Column(Float, nullable=True)
    normal_range_text = Column(String(200), nullable=True)  # free-text range when not numeric
    price = Column(Float, nullable=True, default=0.0)
    turnaround_hours = Column(Integer, nullable=True, default=24)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    results = relationship("LabResult", back_populates="lab_test")
