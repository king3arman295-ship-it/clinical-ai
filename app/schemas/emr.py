from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.common.enums import (
    ReportType,
    ConditionStatus,
    Severity,
)


# ═════════════════════════════════════════════════════════════
# Medical History
# ═════════════════════════════════════════════════════════════

class MedicalHistoryCreate(BaseModel):
    patient_id: int
    condition: str
    diagnosed_date: date | None = None
    status: ConditionStatus = ConditionStatus.ACTIVE
    notes: str | None = None


class MedicalHistoryUpdate(BaseModel):
    condition: str | None = None
    diagnosed_date: date | None = None
    status: ConditionStatus | None = None
    notes: str | None = None


class MedicalHistoryResponse(BaseModel):
    id: int
    patient_id: int
    condition: str
    diagnosed_date: date | None
    status: ConditionStatus
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Patient Reports
# ═════════════════════════════════════════════════════════════

class PatientReportResponse(BaseModel):
    id: int
    patient_id: int
    appointment_id: int | None
    doctor_id: int | None
    report_name: str
    report_type: ReportType
    file_path: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Prescription Items
# ═════════════════════════════════════════════════════════════

class PrescriptionItemCreate(BaseModel):
    medicine_name: str
    form: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    instructions: str | None = None
    quantity: int | None = None


class PrescriptionItemResponse(BaseModel):
    id: int
    prescription_id: int
    medicine_name: str
    form: str | None = None
    dosage: str | None
    frequency: str | None
    duration: str | None
    instructions: str | None
    quantity: int | None = None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Prescriptions
# ═════════════════════════════════════════════════════════════

class PrescriptionCreate(BaseModel):
    # OPD: set appointment_id. IPD/ward round: set admission_id instead.
    # Exactly one of the two must be provided.
    appointment_id: int | None = None
    admission_id: int | None = None
    patient_id: int
    doctor_id: int
    diagnosis: str | None = None
    advice: str | None = None
    items: list[PrescriptionItemCreate] = []


class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: int | None
    admission_id: int | None
    patient_id: int
    doctor_id: int
    diagnosis: str | None
    advice: str | None
    created_at: datetime
    items: list[PrescriptionItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Doctor Notes
# ═════════════════════════════════════════════════════════════

class DoctorNoteCreate(BaseModel):
    appointment_id: int
    patient_id: int
    doctor_id: int
    note: str


class DoctorNoteResponse(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    note: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Patient Vitals
# ═════════════════════════════════════════════════════════════

class PatientVitalCreate(BaseModel):
    appointment_id: int
    patient_id: int
    height: float | None = None
    weight: float | None = None
    temperature: float | None = None
    blood_pressure: str | None = None
    pulse: int | None = None
    oxygen_level: float | None = None


class PatientVitalResponse(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    height: float | None
    weight: float | None
    temperature: float | None
    blood_pressure: str | None
    pulse: int | None
    oxygen_level: float | None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Allergies
# ═════════════════════════════════════════════════════════════

class PatientAllergyCreate(BaseModel):
    patient_id: int
    allergy_name: str
    reaction: str | None = None
    notes: str | None = None


class PatientAllergyUpdate(BaseModel):
    allergy_name: str | None = None
    reaction: str | None = None
    notes: str | None = None


class PatientAllergyResponse(BaseModel):
    id: int
    patient_id: int
    allergy_name: str
    reaction: str | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Diagnoses
# ═════════════════════════════════════════════════════════════

class DiagnosisCreate(BaseModel):
    appointment_id: int
    patient_id: int
    diagnosis: str
    severity: Severity | None = None
    notes: str | None = None


class DiagnosisResponse(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    diagnosis: str
    severity: Severity | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Patient Timeline (Full EMR)
# ═════════════════════════════════════════════════════════════

class PatientTimelineResponse(BaseModel):
    patient_id: int
    patient_name: str
    phone: str
    email: str | None

    medical_history: list[MedicalHistoryResponse] = []
    allergies: list[PatientAllergyResponse] = []
    reports: list[PatientReportResponse] = []
    prescriptions: list[PrescriptionResponse] = []
    diagnoses: list[DiagnosisResponse] = []
    vitals: list[PatientVitalResponse] = []
    doctor_notes: list[DoctorNoteResponse] = []
    lab_orders: list[dict] = []
