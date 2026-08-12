from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class BillItemOut(BaseModel):
    id: int | None = None
    category: str
    description: str
    details: str | None = None
    quantity: float = 1.0
    unit_price: float = 0.0
    amount: float = 0.0
    reference_type: str | None = None
    reference_id: int | None = None

    class Config:
        from_attributes = True


class BillOut(BaseModel):
    id: int
    bill_number: str
    patient_id: int
    patient_name: str
    patient_phone: str | None = None
    patient_email: str | None = None
    appointment_id: int | None = None
    admission_id: int | None = None
    status: str
    subtotal: float
    discount: float
    tax: float
    total: float
    currency: str = "PKR"
    notes: str | None = None
    payment_method: str | None = None
    issued_by: int | None = None
    issued_at: datetime | None = None
    paid_at: datetime | None = None
    items: list[BillItemOut] = []
    category_totals: dict[str, float] = {}

    class Config:
        from_attributes = True


class BillPreviewOut(BaseModel):
    patient_id: int
    patient_name: str
    patient_phone: str | None = None
    patient_email: str | None = None
    appointment_id: int | None = None
    admission_id: int | None = None
    items: list[BillItemOut] = []
    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    currency: str = "PKR"
    category_totals: dict[str, float] = {}
    warnings: list[str] = []
    skipped_already_billed: int = 0


class BillCreateRequest(BaseModel):
    patient_id: int
    discount: float = Field(default=0.0, ge=0)
    tax: float = Field(default=0.0, ge=0)
    notes: str | None = None
    include_categories: list[str] | None = None
    # Scope to one episode of care (recommended)
    appointment_id: int | None = None
    admission_id: int | None = None
    # Default True — do not charge lines already on a non-cancelled bill
    unbilled_only: bool = True


class BillPayRequest(BaseModel):
    payment_method: str = Field(default="cash", description="cash | card | transfer | insurance")
    notes: str | None = None


class ServicePricingItem(BaseModel):
    key: str
    label: str
    amount: float
    description: str | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ServicePricingUpdate(BaseModel):
    amount: float
    label: str | None = None
    description: str | None = None
