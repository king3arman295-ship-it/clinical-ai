from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.core.database import Base
from sqlalchemy.orm import relationship


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(150), nullable=False)

    specialization = Column(String(100), nullable=False)

    qualification = Column(String(100))

    phone = Column(String(20), unique=True)

    email = Column(String(100), unique=True)

    consultation_fee = Column(Integer)

    experience_years = Column(Integer)

    available = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    
    # Foreign key to User
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        unique=True,
    )

    # Relationship to User
    user = relationship(
        "User",
        back_populates="doctor",
        foreign_keys="Doctor.user_id",
    )
    
    schedules = relationship(
        "DoctorSchedule",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    fcm_token = Column(
    String,
    nullable=True,
    )