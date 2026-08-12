from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class NurseBedAssignment(Base):
    """Maps a nurse (user) to the beds they are responsible for."""

    __tablename__ = "nurse_bed_assignments"

    id = Column(Integer, primary_key=True, index=True)

    nurse_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    bed_id = Column(
        Integer,
        ForeignKey("beds.id"),
        nullable=False,
        index=True,
    )

    assigned_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    is_active = Column(Boolean, nullable=False, default=True)

    assigned_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    nurse = relationship("User", foreign_keys=[nurse_user_id])
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])
    bed = relationship("Bed", backref="nurse_assignments")

    __table_args__ = (
        UniqueConstraint(
            "nurse_user_id",
            "bed_id",
            name="uq_nurse_bed",
        ),
    )
