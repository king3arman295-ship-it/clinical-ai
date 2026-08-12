from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.auth.dependencies import get_current_user
from app.auth.roles import require_roles

from app.dependencies.services import get_admission_service
from app.services.admission_service import AdmissionService

from app.schemas.admission import (
    WardCreate,
    WardUpdate,
    WardResponse,
    BedCreate,
    BedUpdate,
    BedResponse,
    BedMapEntry,
    AdmissionRequestCreate,
    AdmissionResponse,
    BedAllocationRequest,
    DischargeRequest,
    AdmissionNoteCreate,
    AdmissionNoteResponse,
    AdmissionConditionUpdate,
    PatientAdmissionView,
)

router = APIRouter(
    prefix="/admissions",
    tags=["Admissions"],
)

ADMISSION_MANAGERS = ("admin", "admission_head")
CLINICAL_STAFF = ("admin", "doctor")


# ═════════════════════════════════════════════════════════════
# Wards (setup/admin)
# ═════════════════════════════════════════════════════════════
@router.post("/wards", response_model=WardResponse)
def create_ward(
    ward: WardCreate,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles("admin", "admission_head")),
):
    result = service.create_ward(db, ward)
    return result.data


@router.get("/wards", response_model=list[WardResponse])
def list_wards(
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    result = service.get_wards(db)
    return result.data


@router.put("/wards/{ward_id}", response_model=WardResponse)
def update_ward(
    ward_id: int,
    ward: WardUpdate,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles("admin", "admission_head")),
):
    result = service.update_ward(db, ward_id, ward)
    return result.data


# ═════════════════════════════════════════════════════════════
# Beds (setup/admin)
# ═════════════════════════════════════════════════════════════
@router.post("/beds", response_model=BedResponse)
def create_bed(
    bed: BedCreate,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles("admin", "admission_head")),
):
    result = service.create_bed(db, bed)
    return result.data


@router.get("/beds", response_model=list[BedResponse])
def list_beds(
    ward_id: int | None = None,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    result = service.get_beds(db, ward_id)
    return result.data


@router.put("/beds/{bed_id}", response_model=BedResponse)
def update_bed(
    bed_id: int,
    bed: BedUpdate,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles("admin", "admission_head")),
):
    result = service.update_bed(db, bed_id, bed)
    return result.data


@router.get("/bed-map", response_model=list[BedMapEntry])
def get_bed_map(
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles(*ADMISSION_MANAGERS)),
):
    """Live bed-map for the Admission Head's dashboard."""
    result = service.get_bed_map(db)
    return result.data


# ═════════════════════════════════════════════════════════════
# Admission Requests — raised by the doctor from a patient's EMR
# ═════════════════════════════════════════════════════════════
@router.post("/requests", response_model=AdmissionResponse)
def create_admission_request(
    admission: AdmissionRequestCreate,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    doctor_id = current_user.get("doctor_id")
    if not doctor_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Doctor access required.")

    result = service.create_admission_request(db, doctor_id, admission)
    return result.data


@router.get("/requests/pending", response_model=list[AdmissionResponse])
def get_pending_requests(
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles(*ADMISSION_MANAGERS)),
):
    """Admission Head's incoming queue."""
    result = service.get_pending_admissions(db)
    return result.data


@router.get("/me", response_model=list[PatientAdmissionView])
def get_my_admissions(
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    """Patient-facing: their own current + past admissions, in
    plain language (ward/bed labels, doctor name) with no internal
    IDs and no clinical rounds notes."""
    patient_id = current_user.get("patient_id")
    if not patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")

    result = service.get_my_admissions(db, patient_id)
    return result.data


@router.get("/{admission_id}", response_model=AdmissionResponse)
def get_admission(
    admission_id: int,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    result = service.get_admission_by_id(db, admission_id)
    return result.data


@router.get("/patient/{patient_id}", response_model=list[AdmissionResponse])
def get_patient_admissions(
    patient_id: int,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    if current_user.get("role") == "patient" and current_user.get("patient_id") != patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="You can only view your own admissions.")

    result = service.get_admissions_for_patient(db, patient_id)
    return result.data


@router.get("/doctor/{doctor_id}", response_model=list[AdmissionResponse])
def get_doctor_admissions(
    doctor_id: int,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    result = service.get_admissions_for_doctor(db, doctor_id)
    return result.data


# ═════════════════════════════════════════════════════════════
# Bed Allocation — Admission Head fulfils the request
# ═════════════════════════════════════════════════════════════
@router.put("/{admission_id}/allocate-bed", response_model=AdmissionResponse)
def allocate_bed(
    admission_id: int,
    allocation: BedAllocationRequest,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles(*ADMISSION_MANAGERS)),
):
    result = service.allocate_bed(db, admission_id, allocation)
    return result.data


# ═════════════════════════════════════════════════════════════
# Discharge — doctor writes the summary, bed is freed immediately
# ═════════════════════════════════════════════════════════════
@router.put("/{admission_id}/discharge", response_model=AdmissionResponse)
def discharge_patient(
    admission_id: int,
    discharge: DischargeRequest,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles(*CLINICAL_STAFF, "admission_head")),
):
    result = service.discharge_patient(db, admission_id, discharge)
    return result.data


@router.put("/{admission_id}/condition", response_model=AdmissionResponse)
def update_condition(
    admission_id: int,
    condition: AdmissionConditionUpdate,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(require_roles(*CLINICAL_STAFF)),
):
    result = service.update_condition(db, admission_id, condition)
    return result.data


# ═════════════════════════════════════════════════════════════
# Rounds / Progress Notes
# ═════════════════════════════════════════════════════════════
@router.post(
    "/{admission_id}/notes",
    response_model=AdmissionNoteResponse,
)
def add_admission_note(
    admission_id: int,
    note: AdmissionNoteCreate,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    doctor_id = current_user.get("doctor_id")
    if not doctor_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Doctor access required.")

    result = service.add_admission_note(db, admission_id, doctor_id, note)
    return result.data


@router.get(
    "/{admission_id}/notes",
    response_model=list[AdmissionNoteResponse],
)
def get_admission_notes(
    admission_id: int,
    db: Session = Depends(get_db),
    service: AdmissionService = Depends(get_admission_service),
    current_user=Depends(get_current_user),
):
    result = service.get_admission_notes(db, admission_id)
    return result.data


@router.post("/{admission_id}/cancel")
def cancel_admission_request(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ADMISSION_MANAGERS)),
    service: AdmissionService = Depends(get_admission_service),
):
    """Cancel a pending admission request; notifies the doctor and patient."""
    result = service.cancel_admission_request(db, admission_id)
    return {"message": result.message, "data": result.data}
