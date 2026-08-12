from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
)

from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import BedStatus


class Bed(Base):
    __tablename__ = "beds"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    ward_id = Column(
        Integer,
        ForeignKey("wards.id"),
        nullable=False,
    )

    bed_number = Column(
        String(20),
        nullable=False,
    )

    # vacant / occupied / maintenance — see app.common.enums.BedStatus
    status = Column(
        String(20),
        nullable=False,
        default=BedStatus.VACANT.value,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------
    ward = relationship(
        "Ward",
        back_populates="beds",
    )

    admissions = relationship(
        "Admission",
        back_populates="bed",
    )

    __table_args__ = (
        UniqueConstraint(
            "ward_id",
            "bed_number",
            name="uq_bed_ward_number",
        ),
    )
