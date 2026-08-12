from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import (
    LabOrderStatus,
    LabSampleType,
    LabTestCategory,
)


# ═════════════════════════════════════════════════════════════
# Lab Test (catalog)
# ═════════════════════════════════════════════════════════════
class LabTestCreate(BaseModel):
    name: str
    code: str | None = None
    category: LabTestCategory = LabTestCategory.OTHER
    sample_type: LabSampleType = LabSampleType.BLOOD
    description: str | None = None
    unit: str | None = None
    normal_range_min: float | None = None
    normal_range_max: float | None = None
    normal_range_text: str | None = None
    price: float | None = 0.0
    turnaround_hours: int | None = 24
    is_active: bool = True


class LabTestUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    category: LabTestCategory | None = None
    sample_type: LabSampleType | None = None
    description: str | None = None
    unit: str | None = None
    normal_range_min: float | None = None
    normal_range_max: float | None = None
    normal_range_text: str | None = None
    price: float | None = None
    turnaround_hours: int | None = None
    is_active: bool | None = None


class LabTestResponse(BaseModel):
    id: int
    name: str
    code: str | None
    category: str
    sample_type: str
    description: str | None
    unit: str | None
    normal_range_min: float | None
    normal_range_max: float | None
    normal_range_text: str | None
    price: float | None
    turnaround_hours: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Lab Result
# ═════════════════════════════════════════════════════════════
class LabResultCreate(BaseModel):
    lab_test_id: int
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    is_abnormal: bool = False
    remarks: str | None = None


class LabResultEnter(BaseModel):
    """Enter / update a single result value."""
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    is_abnormal: bool = False
    remarks: str | None = None


class LabResultResponse(BaseModel):
    id: int
    lab_order_id: int
    lab_test_id: int
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    is_abnormal: bool
    remarks: str | None
    status: str
    entered_by: int | None
    entered_at: datetime | None
    verified_by: int | None
    verified_at: datetime | None
    created_at: datetime

    # Denormalized
    test_name: str | None = None
    test_code: str | None = None
    sample_type: str | None = None
    normal_range_text: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Lab Order
# ═════════════════════════════════════════════════════════════
class LabOrderCreate(BaseModel):
    patient_id: int
    ordered_by_doctor_id: int
    test_ids: list[int] = Field(..., min_length=1)
    appointment_id: int | None = None
    admission_id: int | None = None
    prescription_id: int | None = None
    priority: str = "routine"  # routine / urgent / stat
    clinical_notes: str | None = None


class LabOrderResponse(BaseModel):
    id: int
    patient_id: int | None = None
    ordered_by_doctor_id: int | None = None
    appointment_id: int | None
    admission_id: int | None
    prescription_id: int | None
    status: LabOrderStatus
    priority: str
    clinical_notes: str | None
    sample_collected_at: datetime | None
    sample_collected_by: int | None
    completed_at: datetime | None
    reported_by: int | None
    created_at: datetime
    updated_at: datetime | None

    # Display helpers
    patient_name: str | None = None
    doctor_name: str | None = None
    source: str = "opd"  # opd / ipd / walk_in
    ward_bed_label: str | None = None
    order_source: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    results: list[LabResultResponse] = []

    model_config = ConfigDict(from_attributes=True)


class LabOrderStatusUpdate(BaseModel):
    status: LabOrderStatus
    note: str | None = None


class WalkInLabOrderCreate(BaseModel):
    """Lab counter order — walk-in guest or registered patient (optional doctor)."""
    test_ids: list[int] = Field(..., min_length=1)
    patient_id: int | None = None
    ordered_by_doctor_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    priority: str = "routine"
    clinical_notes: str | None = None
