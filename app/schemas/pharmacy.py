from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.common.enums import MedicineForm, PharmacyOrderStatus


# ═════════════════════════════════════════════════════════════
# Medicine (inventory master list)
# ═════════════════════════════════════════════════════════════
class MedicineCreate(BaseModel):
    name: str
    form: MedicineForm = MedicineForm.TABLET
    dosage: str | None = None
    unit: str = "units"
    stock_qty: int = 0
    reorder_threshold: int = 10
    unit_price: float = 50.0
    batch_number: str | None = None
    expiry_date: date | None = None


class MedicineUpdate(BaseModel):
    name: str | None = None
    form: MedicineForm | None = None
    dosage: str | None = None
    unit: str | None = None
    reorder_threshold: int | None = None
    unit_price: float | None = None
    batch_number: str | None = None
    expiry_date: date | None = None


class MedicineRestock(BaseModel):
    quantity: int


class MedicineResponse(BaseModel):
    id: int
    name: str
    form: MedicineForm
    dosage: str | None = None
    unit: str
    stock_qty: int
    reorder_threshold: int
    unit_price: float = 50.0
    batch_number: str | None = None
    expiry_date: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Pharmacy Order (fulfillment queue for a prescription item)
# ═════════════════════════════════════════════════════════════
class PharmacyOrderResponse(BaseModel):
    id: int
    prescription_item_id: int
    patient_id: int
    medicine_id: int | None
    status: PharmacyOrderStatus
    dispensed_by: int | None
    dispensed_at: datetime | None
    created_at: datetime

    # Inventory units to dispense (course: times/day × days)
    quantity: int = 1
    # tablet | capsule | syrup | injection | drip | …
    form: str | None = None
    # prescription | course  (DB column on pharmacy_orders)
    # NOTE: do not default to "opd" — that wiped "course" in the API.
    source: str | None = "prescription"
    course_item_id: int | None = None

    # Denormalized display fields, filled in by the service layer.
    medicine_name: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    patient_name: str | None = None
    prescribing_doctor_id: int | None = None

    # OPD vs IPD display (not the DB source column)
    order_source: str | None = None
    care_setting: str | None = None
    source_label: str | None = None
    admission_id: int | None = None
    ward_bed_label: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PharmacyOrderDispense(BaseModel):
    """No body fields required — the dispensing user comes from the
    auth token — but kept as a schema in case a quantity override or
    note is needed later."""

    note: str | None = None


# ═════════════════════════════════════════════════════════════
# Medication Administration Record (IPD ongoing dosing)
# ═════════════════════════════════════════════════════════════
class MedicationAdministrationCreate(BaseModel):
    medicine_id: int
    scheduled_time: datetime | None = None


class MedicationAdministrationResponse(BaseModel):
    id: int
    admission_id: int
    medicine_id: int
    scheduled_time: datetime | None
    given_at: datetime
    given_by: int | None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Walk-in / OTC counter sale (no doctor order)
# ═════════════════════════════════════════════════════════════
class WalkInDispenseRequest(BaseModel):
    medicine_id: int
    quantity: int = 1
    customer_name: str | None = None
    customer_phone: str | None = None
    patient_id: int | None = None
    notes: str | None = None


class WalkInSaleResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_name: str | None = None
    form: str | None = None
    quantity: int
    customer_name: str | None = None
    customer_phone: str | None = None
    patient_id: int | None = None
    notes: str | None = None
    unit_price: float = 0.0
    total_price: float = 0.0
    sold_by: int | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
