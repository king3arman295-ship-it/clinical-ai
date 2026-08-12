from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.common.enums import LabOrderStatus


class LabOrder(Base):
    """
    A laboratory order for a patient.
    Can originate from an OPD appointment, an IPD admission,
    or a free-standing doctor request.
    """

    __tablename__ = "lab_orders"

    id = Column(Integer, primary_key=True, index=True)

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    ordered_by_doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)

    # Optional links — at least one clinical context is preferred
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    admission_id = Column(Integer, ForeignKey("admissions.id"), nullable=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default=LabOrderStatus.PENDING.value,
    )
    priority = Column(String(20), nullable=False, default="routine")  # routine / urgent / stat
    clinical_notes = Column(Text, nullable=True)

    # doctor | walk_in  (counter orders without a prescribing doctor)
    order_source = Column(String(30), nullable=False, default="doctor", server_default="doctor")
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)

    sample_collected_at = Column(DateTime(timezone=True), nullable=True)
    sample_collected_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    completed_at = Column(DateTime(timezone=True), nullable=True)
    reported_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    patient = relationship("Patient", back_populates="lab_orders")
    ordered_by_doctor = relationship("Doctor", foreign_keys=[ordered_by_doctor_id])
    appointment = relationship("Appointment", foreign_keys=[appointment_id])
    admission = relationship("Admission", foreign_keys=[admission_id])
    prescription = relationship("Prescription", foreign_keys=[prescription_id])
    sample_collector = relationship("User", foreign_keys=[sample_collected_by])
    reporter = relationship("User", foreign_keys=[reported_by])
    results = relationship(
        "LabResult",
        back_populates="lab_order",
        cascade="all, delete-orphan",
    )
