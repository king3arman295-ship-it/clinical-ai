from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Time,
    ForeignKey,
)

from sqlalchemy.orm import relationship

from app.core.database import Base


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=False,
    )

    day_of_week = Column(
        String(20),
        nullable=False,
    )
    # Examples:
    # Monday
    # Tuesday
    # Wednesday
    # Thursday
    # Friday
    # Saturday
    # Sunday

    start_time = Column(
        Time,
        nullable=False,
    )

    end_time = Column(
        Time,
        nullable=False,
    )

    slot_duration = Column(
        Integer,
        default=30,
        nullable=False,
    )
    # Minutes:
    # 15
    # 20
    # 30
    # 45
    # 60

    is_available = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    doctor = relationship(
        "Doctor",
        back_populates="schedules",
    )