import os

from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    Form,
)
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.services.emr_service import EMRService
from app.dependencies.services import get_emr_service
from app.auth.roles import require_roles
from app.auth.dependencies import get_current_user
from app.exceptions.exceptions import UnauthorizedException

from app.schemas.laboratory import LabOrderCreate
from app.schemas.emr import (
    MedicalHistoryCreate,
    MedicalHistoryUpdate,
    MedicalHistoryResponse,
    PatientReportResponse,
    PrescriptionCreate,
    PrescriptionResponse,
    DoctorNoteCreate,
    DoctorNoteResponse,
    PatientVitalCreate,
    PatientVitalResponse,
    PatientAllergyCreate,
    PatientAllergyUpdate,
    PatientAllergyResponse,
    DiagnosisCreate,
    DiagnosisResponse,
    PatientTimelineResponse,
)

router = APIRouter(
    prefix="/emr",
    tags=["EMR"],
)


def _require_patient_record_access(current_user, patient_id: int) -> None:
    """Permit staff access, but never let a patient read another patient's EMR."""
    if current_user["role"] not in ("admin", "doctor", "patient", "admission_head", "pharmacist", "lab_technician"):
        raise UnauthorizedException("You are not authorized to view medical records.")
    if (
        current_user["role"] == "patient"
        and current_user.get("patient_id") != patient_id
    ):
        raise UnauthorizedException(
            "You are not authorized to view this patient's medical record."
        )


def _require_report_upload_access(current_user, patient_id: int) -> None:
    """Allow staff uploads and allow a patient to upload only to their own EMR."""
    if current_user["role"] in ("admin", "doctor", "receptionist"):
        return
    if (
        current_user["role"] == "patient"
        and current_user.get("patient_id") == patient_id
    ):
        return
    raise UnauthorizedException("You are not authorized to upload to this medical record.")


def _require_report_access(current_user, report) -> None:
    """Apply the appointment-based sharing rule when a doctor opens one report."""
    _require_patient_record_access(current_user, report.patient_id)
    if current_user["role"] == "doctor":
        if (
            report.appointment is None
            or report.appointment.doctor_id != current_user.get("doctor_id")
        ):
            raise UnauthorizedException(
                "This document was not shared with you by the patient."
            )


# ═════════════════════════════════════════════════════════════
# Medical History
# ═════════════════════════════════════════════════════════════

@router.post(
    "/medical-history",
    response_model=MedicalHistoryResponse,
)
def add_medical_history(
    data: MedicalHistoryCreate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.add_medical_history(db, data)
    return result.data


@router.get(
    "/patients/{patient_id}/medical-history",
    response_model=list[MedicalHistoryResponse],
)
def get_patient_medical_history(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_patient_medical_history(
        db, patient_id,
    )
    return result.data


@router.put(
    "/medical-history/{history_id}",
    response_model=MedicalHistoryResponse,
)
def update_medical_history(
    history_id: int,
    data: MedicalHistoryUpdate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.update_medical_history(
        db, history_id, data,
    )
    return result.data


@router.delete("/medical-history/{history_id}")
def delete_medical_history(
    history_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.delete_medical_history(
        db, history_id,
    )
    return {
        "message": "Medical history deleted successfully."
    }


# ═════════════════════════════════════════════════════════════
# Patient Reports (File Upload)
# ═════════════════════════════════════════════════════════════

@router.post(
    "/reports/upload",
    response_model=PatientReportResponse,
)
def upload_report(
    patient_id: int = Form(...),
    report_name: str = Form(...),
    report_type: str = Form(...),
    appointment_id: int | None = Form(None),
    doctor_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(get_current_user),
):
    _require_report_upload_access(current_user, patient_id)
    result = service.upload_report(
        db=db,
        patient_id=patient_id,
        report_name=report_name,
        report_type=report_type,
        file=file,
        appointment_id=appointment_id,
        doctor_id=doctor_id,
    )
    return result.data


@router.get(
    "/patients/{patient_id}/reports",
    response_model=list[PatientReportResponse],
)
def get_patient_reports(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(get_current_user),
):
    _require_patient_record_access(current_user, patient_id)
    doctor_id = current_user.get("doctor_id") if current_user["role"] == "doctor" else None
    result = service.get_patient_reports(
        db, patient_id, doctor_id,
    )
    return result.data


@router.get(
    "/reports/{report_id}",
    response_model=PatientReportResponse,
)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(get_current_user),
):
    result = service.get_report_by_id(db, report_id)
    _require_report_access(current_user, result.data)
    return result.data


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(get_current_user),
):
    result = service.get_report_by_id(db, report_id)
    report = result.data
    _require_report_access(current_user, report)
    # __file__ is app/api/v1/emr.py, so we need to go up FOUR levels
    # (v1 -> api -> app -> project root) to reach the folder that
    # contains "uploads/reports/...". The previous version only went
    # up three levels, which resolved into the "app" folder instead of
    # the project root, so the file was never found and every
    # download (including the doctor's) failed with a 404.
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    file_path = os.path.join(
        project_root,
        report.file_path,
    )
    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found.")

    # Prefer a proper download name + media type so HTML lab reports
    # open correctly in the browser and PDF/images still download fine.
    original = report.file_path or ""
    ext = os.path.splitext(original)[1].lower() or ""
    safe_name = (report.report_name or f"report_{report_id}").strip()
    # strip characters that break Content-Disposition
    for ch in '\\/:*?"<>|':
        safe_name = safe_name.replace(ch, "_")
    if ext and not safe_name.lower().endswith(ext):
        safe_name = f"{safe_name}{ext}"

    media_map = {
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".txt": "text/plain",
    }
    media_type = media_map.get(ext)

    kwargs = {"filename": safe_name}
    if media_type:
        kwargs["media_type"] = media_type
    # HTML lab reports: open inline so doctor/patient can view & print
    if ext in (".html", ".htm"):
        kwargs["content_disposition_type"] = "inline"

    return FileResponse(file_path, **kwargs)

@router.delete("/reports/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    service.delete_report(db, report_id)
    return {
        "message": "Report deleted successfully."
    }


# ═════════════════════════════════════════════════════════════
# Prescriptions
# ═════════════════════════════════════════════════════════════

@router.post(
    "/prescriptions",
    response_model=PrescriptionResponse,
)
def create_prescription(
    data: PrescriptionCreate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.create_prescription(db, data)
    return result.data


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=PrescriptionResponse,
)
def get_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_prescription(
        db, prescription_id,
    )
    return result.data


@router.get(
    "/patients/{patient_id}/prescriptions",
    response_model=list[PrescriptionResponse],
)
def get_prescriptions_by_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_prescriptions_by_patient(
        db, patient_id,
    )
    return result.data


@router.get(
    "/appointments/{appointment_id}/prescriptions",
    response_model=list[PrescriptionResponse],
)
def get_prescriptions_by_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_prescriptions_by_appointment(
        db, appointment_id,
    )
    return result.data


# ═════════════════════════════════════════════════════════════
# Doctor Notes
# ═════════════════════════════════════════════════════════════

@router.post(
    "/doctor-notes",
    response_model=DoctorNoteResponse,
)
def add_doctor_note(
    data: DoctorNoteCreate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("doctor")
    ),
):
    result = service.add_doctor_note(db, data)
    return result.data


@router.get(
    "/appointments/{appointment_id}/doctor-notes",
    response_model=list[DoctorNoteResponse],
)
def get_notes_by_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("doctor")
    ),
):
    result = service.get_notes_by_appointment(
        db, appointment_id,
    )
    return result.data


@router.get(
    "/patients/{patient_id}/doctor-notes",
    response_model=list[DoctorNoteResponse],
)
def get_notes_by_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("doctor")
    ),
):
    result = service.get_notes_by_patient(
        db, patient_id,
    )
    return result.data


# ═════════════════════════════════════════════════════════════
# Vitals
# ═════════════════════════════════════════════════════════════

@router.post(
    "/vitals",
    response_model=PatientVitalResponse,
)
def record_vitals(
    data: PatientVitalCreate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.record_vitals(db, data)
    return result.data


@router.get(
    "/patients/{patient_id}/vitals",
    response_model=list[PatientVitalResponse],
)
def get_vitals_by_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_vitals_by_patient(
        db, patient_id,
    )
    return result.data


@router.get(
    "/appointments/{appointment_id}/vitals",
    response_model=list[PatientVitalResponse],
)
def get_vitals_by_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_vitals_by_appointment(
        db, appointment_id,
    )
    return result.data


# ═════════════════════════════════════════════════════════════
# Allergies
# ═════════════════════════════════════════════════════════════

@router.post(
    "/allergies",
    response_model=PatientAllergyResponse,
)
def add_allergy(
    data: PatientAllergyCreate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.add_allergy(db, data)
    return result.data


@router.get(
    "/patients/{patient_id}/allergies",
    response_model=list[PatientAllergyResponse],
)
def get_patient_allergies(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_patient_allergies(
        db, patient_id,
    )
    return result.data


@router.put(
    "/allergies/{allergy_id}",
    response_model=PatientAllergyResponse,
)
def update_allergy(
    allergy_id: int,
    data: PatientAllergyUpdate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.update_allergy(
        db, allergy_id, data,
    )
    return result.data


@router.delete("/allergies/{allergy_id}")
def delete_allergy(
    allergy_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    service.delete_allergy(db, allergy_id)
    return {
        "message": "Allergy deleted successfully."
    }


# ═════════════════════════════════════════════════════════════
# Diagnoses
# ═════════════════════════════════════════════════════════════

@router.post(
    "/diagnoses",
    response_model=DiagnosisResponse,
)
def add_diagnosis(
    data: DiagnosisCreate,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.add_diagnosis(db, data)
    return result.data


@router.get(
    "/patients/{patient_id}/diagnoses",
    response_model=list[DiagnosisResponse],
)
def get_diagnoses_by_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_diagnoses_by_patient(
        db, patient_id,
    )
    return result.data


@router.get(
    "/appointments/{appointment_id}/diagnoses",
    response_model=list[DiagnosisResponse],
)
def get_diagnoses_by_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(
        require_roles("admin", "doctor")
    ),
):
    result = service.get_diagnoses_by_appointment(
        db, appointment_id,
    )
    return result.data


# ═════════════════════════════════════════════════════════════
# Patient Timeline (Full EMR)
# ═════════════════════════════════════════════════════════════

@router.get(
    "/patients/{patient_id}/timeline",
    response_model=PatientTimelineResponse,
)
def get_patient_timeline(
    patient_id: int,
    db: Session = Depends(get_db),
    service: EMRService = Depends(get_emr_service),
    current_user=Depends(get_current_user),
):
    """Return a complete EMR only to staff or to the patient who owns it."""
    _require_patient_record_access(current_user, patient_id)
    doctor_id = current_user.get("doctor_id") if current_user["role"] == "doctor" else None

    result = service.get_patient_timeline(
        db, patient_id, doctor_id,
    )
    return result.data


# ═════════════════════════════════════════════════════════
# Lab Orders (doctor orders tests during appointment)
# ═════════════════════════════════════════════════════════
@router.post(
    "/lab-orders",
    summary="Order lab tests for a patient (from appointment or admission)",
)
def create_lab_order(
    data: LabOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor")),
    service: EMRService = Depends(get_emr_service),
):
    # Force ordered_by_doctor_id from token when doctor
    if current_user.get("role") == "doctor" and current_user.get("doctor_id"):
        data.ordered_by_doctor_id = current_user["doctor_id"]

    result = service.create_lab_order(db, data)
    return {"message": result.message, "data": result.data}

