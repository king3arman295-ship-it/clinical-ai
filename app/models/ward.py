from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Ward(Base):
    __tablename__ = "wards"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(100),
        nullable=False,
    )

    # general / icu / private / pediatric — see app.common.enums.WardType
    type = Column(
        String(20),
        nullable=False,
    )

    total_beds = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Charge per night used by Billing Department
    daily_rate = Column(
        Float,
        nullable=False,
        default=2000.0,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    beds = relationship(
        "Bed",
        back_populates="ward",
        cascade="all, delete-orphan",
    )
