from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.auth.dependencies import get_current_user
from app.auth.roles import require_roles

from app.dependencies.services import get_laboratory_service
from app.services.laboratory_service import LaboratoryService

from app.schemas.laboratory import (
    LabTestCreate,
    LabTestUpdate,
    LabTestResponse,
    LabOrderCreate, WalkInLabOrderCreate,
    LabOrderResponse,
    LabResultEnter,
    LabResultResponse,
)

router = APIRouter(
    prefix="/laboratory",
    tags=["Laboratory"],
)

LAB_STAFF = ("admin", "lab_technician", "doctor")
LAB_TECH = ("admin", "lab_technician")


# ═════════════════════════════════════════════════════════════
# Lab Test Catalog
# ═════════════════════════════════════════════════════════════
@router.post("/tests", response_model=dict)
def create_lab_test(
    data: LabTestCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "lab_technician")),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.create_test(db, data)
    return {"message": result.message, "data": LabTestResponse.model_validate(result.data)}


@router.get("/tests", response_model=dict)
def list_lab_tests(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.list_tests(db, active_only=active_only)
    return {
        "message": result.message,
        "data": [LabTestResponse.model_validate(t) for t in result.data],
    }


@router.get("/tests/{test_id}", response_model=dict)
def get_lab_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.get_test(db, test_id)
    return {"message": result.message, "data": LabTestResponse.model_validate(result.data)}


@router.patch("/tests/{test_id}", response_model=dict)
def update_lab_test(
    test_id: int,
    data: LabTestUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "lab_technician")),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.update_test(db, test_id, data)
    return {"message": result.message, "data": LabTestResponse.model_validate(result.data)}


# ═════════════════════════════════════════════════════════════
# Lab Orders
# ═════════════════════════════════════════════════════════════
@router.post("/orders", response_model=dict)
def create_lab_order(
    data: LabOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor", "lab_technician")),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.create_order(db, data)
    return {"message": result.message, "data": _order_to_response(result.data)}




@router.post("/walk-in", response_model=dict)
def create_walk_in_lab_order(
    data: WalkInLabOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "lab_technician")),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    """Create a lab order for a walk-in customer (no doctor order required)."""
    result = service.create_walk_in_order(db, data)
    return {"message": result.message, "data": _order_to_response(result.data)}

@router.get("/orders/queue", response_model=dict)
def get_lab_queue(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*LAB_TECH)),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.get_queue(db)
    return {
        "message": result.message,
        "data": [_order_to_response(o) for o in result.data],
    }


@router.get("/orders", response_model=dict)
def list_lab_orders(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*LAB_STAFF)),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.list_orders(db, status=status)
    return {
        "message": result.message,
        "data": [_order_to_response(o) for o in result.data],
    }


@router.get("/orders/{order_id}", response_model=dict)
def get_lab_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.get_order(db, order_id)
    return {"message": result.message, "data": _order_to_response(result.data)}


@router.get("/patients/{patient_id}/orders", response_model=dict)
def get_patient_lab_orders(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    """Staff can view any patient; patients can only view their own orders."""
    from app.exceptions.exceptions import UnauthorizedException

    role = current_user.get("role")
    if role == "patient" and current_user.get("patient_id") != patient_id:
        raise UnauthorizedException("You can only view your own lab orders.")
    if role not in ("admin", "lab_technician", "doctor", "patient", "admission_head"):
        raise UnauthorizedException("Not authorized to view lab orders.")

    result = service.get_patient_orders(db, patient_id)
    return {
        "message": result.message,
        "data": [_order_to_response(o) for o in result.data],
    }


@router.post("/orders/{order_id}/collect-sample", response_model=dict)
def collect_sample(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*LAB_TECH)),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    username = current_user.get("username") or current_user.get("sub")
    result = service.collect_sample(db, order_id, username)
    return {"message": result.message, "data": _order_to_response(result.data)}


@router.patch("/results/{result_id}", response_model=dict)
def enter_result(
    result_id: int,
    data: LabResultEnter,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*LAB_TECH)),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    username = current_user.get("username") or current_user.get("sub")
    result = service.enter_result(db, result_id, data, username)
    return {"message": result.message, "data": LabResultResponse.model_validate(result.data)}


@router.post("/orders/{order_id}/complete", response_model=dict)
def complete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*LAB_TECH)),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    username = current_user.get("username") or current_user.get("sub")
    result = service.complete_order(db, order_id, username)
    return {"message": result.message, "data": _order_to_response(result.data)}


@router.post("/orders/{order_id}/cancel", response_model=dict)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor", "lab_technician")),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    result = service.cancel_order(db, order_id)
    return {"message": result.message, "data": _order_to_response(result.data)}


def _order_to_response(order) -> dict:
    results = []
    for r in getattr(order, "results", None) or []:
        results.append(LabResultResponse.model_validate(r).model_dump())
    base = LabOrderResponse.model_validate(order).model_dump()
    base["results"] = results
    base["order_source"] = getattr(order, "order_source", None) or base.get("order_source")
    base["customer_name"] = getattr(order, "customer_name", None)
    base["customer_phone"] = getattr(order, "customer_phone", None)
    if not base.get("patient_name") and base.get("customer_name"):
        base["patient_name"] = base["customer_name"]
    if getattr(order, "order_source", None) == "walk_in":
        base["source"] = "walk_in"
    return base


@router.get("/orders/{order_id}/report", response_model=dict)
def get_lab_report(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    """Return a formal HTML laboratory result report for a completed order.
    Lab staff, the ordering doctor, admins, and the patient who owns the
    order may view/download it.
    """
    from app.exceptions.exceptions import UnauthorizedException, NotFoundException

    order = service.order_repo.get_by_id(db, order_id)
    if not order:
        raise NotFoundException("Lab order not found.")

    role = current_user.get("role")
    allowed = False
    if role in ("admin", "lab_technician"):
        allowed = True
    elif role == "doctor" and current_user.get("doctor_id") == order.ordered_by_doctor_id:
        allowed = True
    elif role == "doctor":
        # Any doctor treating the patient can view (same spirit as EMR reports)
        allowed = True
    elif role == "patient" and current_user.get("patient_id") == order.patient_id:
        allowed = True

    if not allowed:
        raise UnauthorizedException("You are not authorized to view this lab report.")

    result = service.get_report_html(db, order_id)
    return {"message": result.message, "data": result.data}


@router.get("/orders/{order_id}/report/download")
def download_lab_report_file(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    service: LaboratoryService = Depends(get_laboratory_service),
):
    """Download/view the saved EMR HTML file for a completed lab order."""
    import os
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi import HTTPException
    from app.exceptions.exceptions import UnauthorizedException, NotFoundException, BadRequestException
    from app.models.patient_report import PatientReport

    order = service.order_repo.get_by_id(db, order_id)
    if not order:
        raise NotFoundException("Lab order not found.")
    if order.status != "completed":
        raise BadRequestException("Report is only available for completed orders.")

    role = current_user.get("role")
    allowed = (
        role in ("admin", "lab_technician")
        or role == "doctor"
        or (role == "patient" and current_user.get("patient_id") == order.patient_id)
    )
    if not allowed:
        raise UnauthorizedException("You are not authorized to download this lab report.")

    # Prefer the EMR-stored file if present
    report = (
        db.query(PatientReport)
        .filter(
            PatientReport.patient_id == order.patient_id,
            PatientReport.report_name.ilike(f"%Lab Report #{order.id}%"),
        )
        .order_by(PatientReport.uploaded_at.desc())
        .first()
    )
    if report and report.file_path:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        file_path = os.path.join(project_root, report.file_path)
        if os.path.exists(file_path):
            return FileResponse(
                file_path,
                media_type="text/html",
                filename=f"Lab_Report_{order.id}.html",
                content_disposition_type="inline",
            )

    # Fallback: regenerate HTML
    result = service.get_report_html(db, order_id)
    html = (result.data or {}).get("html") or ""
    return HTMLResponse(content=html)

