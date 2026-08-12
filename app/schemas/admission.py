from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.common.enums import (
    WardType,
    BedStatus,
    AdmissionUrgency,
    AdmissionStatus,
    ConditionFlag,
)


# ═════════════════════════════════════════════════════════════
# Ward
# ═════════════════════════════════════════════════════════════
class WardCreate(BaseModel):
    name: str
    type: WardType = WardType.GENERAL
    total_beds: int = 0
    daily_rate: float = 2000.0


class WardUpdate(BaseModel):
    name: str | None = None
    type: WardType | None = None
    total_beds: int | None = None
    daily_rate: float | None = None


class WardResponse(BaseModel):
    id: int
    name: str
    type: WardType
    total_beds: int
    daily_rate: float = 2000.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Bed
# ═════════════════════════════════════════════════════════════
class BedCreate(BaseModel):
    ward_id: int
    bed_number: str
    status: BedStatus = BedStatus.VACANT


class BedUpdate(BaseModel):
    bed_number: str | None = None
    status: BedStatus | None = None


class BedResponse(BaseModel):
    id: int
    ward_id: int
    bed_number: str
    status: BedStatus
    ward_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BedMapEntry(BaseModel):
    """One row of the Admission Head's live bed-map dashboard."""

    bed_id: int
    ward_id: int
    ward_name: str
    ward_type: WardType
    bed_number: str
    status: BedStatus

    admission_id: int | None = None
    patient_id: int | None = None
    patient_name: str | None = None
    admitted_since: datetime | None = None
    admitting_doctor_id: int | None = None
    admitting_doctor_name: str | None = None
    condition_flag: ConditionFlag | None = None


# ═════════════════════════════════════════════════════════════
# Admission Request (created by the doctor)
# ═════════════════════════════════════════════════════════════
class AdmissionRequestCreate(BaseModel):
    patient_id: int
    reason: str | None = None
    diagnosis: str | None = None
    urgency: AdmissionUrgency = AdmissionUrgency.ROUTINE
    preferred_ward_type: WardType | None = None


# ═════════════════════════════════════════════════════════════
# Bed Allocation (Admission Head fulfils the request)
# ═════════════════════════════════════════════════════════════
class BedAllocationRequest(BaseModel):
    bed_id: int
    admitting_doctor_id: int | None = None


# ═════════════════════════════════════════════════════════════
# Discharge
# ═════════════════════════════════════════════════════════════
class DischargeRequest(BaseModel):
    discharge_summary: str


# ═════════════════════════════════════════════════════════════
# Admission Note (rounds / progress notes)
# ═════════════════════════════════════════════════════════════
class AdmissionNoteCreate(BaseModel):
    note: str
    vitals: str | None = None


class AdmissionNoteResponse(BaseModel):
    id: int
    admission_id: int
    doctor_id: int
    note: str
    vitals: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdmissionConditionUpdate(BaseModel):
    condition_flag: ConditionFlag


# ═════════════════════════════════════════════════════════════
# Admission Response
# ═════════════════════════════════════════════════════════════
class AdmissionResponse(BaseModel):
    id: int
    patient_id: int
    requesting_doctor_id: int
    admitting_doctor_id: int | None
    bed_id: int | None
    reason: str | None
    diagnosis: str | None
    urgency: AdmissionUrgency
    preferred_ward_type: WardType | None
    status: AdmissionStatus
    condition_flag: ConditionFlag | None
    discharge_summary: str | None
    requested_at: datetime
    admitted_at: datetime | None
    discharged_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ═════════════════════════════════════════════════════════════
# Patient-facing admission view — what's ok to show a patient about
# their own stay. Deliberately excludes clinical rounds notes
# (AdmissionNote) and internal bed/ward IDs; shows plain labels instead.
# ═════════════════════════════════════════════════════════════
class PatientAdmissionView(BaseModel):
    id: int
    status: AdmissionStatus
    urgency: AdmissionUrgency
    reason: str | None
    diagnosis: str | None
    ward_name: str | None = None
    bed_number: str | None = None
    admitting_doctor_name: str | None = None
    condition_flag: ConditionFlag | None = None
    discharge_summary: str | None = None
    requested_at: datetime
    admitted_at: datetime | None
    discharged_at: datetime | None
