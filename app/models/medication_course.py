from sqlalchemy import Boolean, (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class MedicationCourse(Base):
    """
    Multi-day IPD medication / drip course ordered by a doctor.
    Nurses implement daily doses and mark them given/held/missed.
    """

    __tablename__ = "medication_courses"

    id = Column(Integer, primary_key=True, index=True)

    admission_id = Column(
        Integer,
        ForeignKey("admissions.id"),
        nullable=False,
        index=True,
    )

    ordered_by_doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=False,
    )

    title = Column(String(200), nullable=False, default="Ward Medication Course")

    # active | completed | stopped
    status = Column(String(20), nullable=False, default="active")

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    duration_days = Column(Integer, nullable=False, default=1)

    clinical_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    admission = relationship("Admission", backref="medication_courses")
    ordered_by_doctor = relationship("Doctor", foreign_keys=[ordered_by_doctor_id])
    items = relationship(
        "MedicationCourseItem",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    doses = relationship(
        "MedicationCourseDose",
        back_populates="course",
        cascade="all, delete-orphan",
    )


class MedicationCourseItem(Base):
    """One medicine or drip line in a multi-day course."""

    __tablename__ = "medication_course_items"

    id = Column(Integer, primary_key=True, index=True)

    course_id = Column(
        Integer,
        ForeignKey("medication_courses.id"),
        nullable=False,
        index=True,
    )

    medicine_id = Column(
        Integer,
        ForeignKey("medicines.id"),
        nullable=True,
    )

    medicine_name = Column(String(200), nullable=False)

    # oral | iv | im | sc | other
    route = Column(String(30), nullable=False, default="oral")

    dosage = Column(String(100), nullable=False)
    frequency = Column(String(50), nullable=False, default="OD")
    # OD=1, BD=2, TID=3, QID=4, or explicit times_per_day
    times_per_day = Column(Integer, nullable=False, default=1)

    # Comma-separated HH:MM e.g. "08:00,14:00,20:00"
    schedule_times = Column(String(120), nullable=True)

    # For IV drips
    drip_rate = Column(String(100), nullable=True)

    instructions = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    # Linked pharmacy fulfillment — nurse may mark "given" only after this is dispensed
    pharmacy_order_id = Column(Integer, ForeignKey("pharmacy_orders.id"), nullable=True)

    course = relationship("MedicationCourse", back_populates="items")
    medicine = relationship("Medicine")
    pharmacy_order = relationship("PharmacyOrder", foreign_keys=[pharmacy_order_id])
    doses = relationship(
        "MedicationCourseDose",
        back_populates="item",
        cascade="all, delete-orphan",
    )


class MedicationCourseDose(Base):
    """Individual scheduled dose for a specific date/time — nurse marks status."""

    __tablename__ = "medication_course_doses"

    id = Column(Integer, primary_key=True, index=True)

    course_id = Column(
        Integer,
        ForeignKey("medication_courses.id"),
        nullable=False,
        index=True,
    )

    course_item_id = Column(
        Integer,
        ForeignKey("medication_course_items.id"),
        nullable=False,
        index=True,
    )

    admission_id = Column(
        Integer,
        ForeignKey("admissions.id"),
        nullable=False,
        index=True,
    )

    scheduled_date = Column(Date, nullable=False, index=True)
    scheduled_time = Column(String(10), nullable=True)  # HH:MM

    # pending | given | held | missed | skipped
    status = Column(String(20), nullable=False, default="pending")

    given_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    given_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)

    # True after patient received a push/in-app reminder for this dose time
    patient_reminded = Column(Boolean, nullable=False, default=False, server_default='false')

    # Link to MAR stock-decrement log when given
    medication_administration_id = Column(
        Integer,
        ForeignKey("medication_administrations.id"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("MedicationCourse", back_populates="doses")
    item = relationship("MedicationCourseItem", back_populates="doses")
    admission = relationship("Admission")
    given_by_user = relationship("User", foreign_keys=[given_by])
