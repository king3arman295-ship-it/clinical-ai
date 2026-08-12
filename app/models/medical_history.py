from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Text,
    ForeignKey,
    Enum,
)

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import ConditionStatus


class MedicalHistory(Base):
    __tablename__ = "patient_medical_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
    )

    condition = Column(
        String(200),
        nullable=False,
    )

    diagnosed_date = Column(
        Date,
        nullable=True,
    )

    status = Column(
        Enum(
            ConditionStatus,
            values_callable=lambda enum: [e.value for e in enum],
            name="condition_status_enum",
        ),
        nullable=False,
        default=ConditionStatus.ACTIVE,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    patient = relationship(
        "Patient",
        back_populates="medical_history",
    )
