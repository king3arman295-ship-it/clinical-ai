from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.auth.roles import require_roles
from app.auth.dependencies import get_current_user
from app.services.billing_service import BillingService
from app.schemas.billing import BillCreateRequest, BillPayRequest, ServicePricingUpdate

router = APIRouter(prefix="/billing", tags=["Billing"])


def get_billing_service() -> BillingService:
    return BillingService()


def _user_id(db: Session, current_user) -> int | None:
    uid = current_user.get("id")
    if uid:
        return int(uid)
    username = current_user.get("username")
    if not username:
        return None
    from app.models.user import User
    user = db.query(User).filter(User.username == username).first()
    return user.id if user else None


@router.get("/patients/search")
def search_patients(
    q: str = Query(..., min_length=1, description="Name, phone, email, or patient id"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing", "receptionist")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.search_patients(db, q)
    return {"message": result.message, "data": result.data}


@router.get("/patients/{patient_id}/episodes")
def list_patient_episodes(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing", "receptionist")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.list_patient_episodes(db, patient_id)
    return {"message": result.message, "data": result.data}


@router.get("/patients/{patient_id}/preview")
def preview_patient_bill(
    patient_id: int,
    discount: float = Query(0),
    tax: float = Query(0),
    appointment_id: int | None = Query(None),
    admission_id: int | None = Query(None),
    unbilled_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing", "receptionist")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.preview_bill(
        db,
        patient_id,
        discount=discount,
        tax=tax,
        appointment_id=appointment_id,
        admission_id=admission_id,
        unbilled_only=unbilled_only,
    )
    return {"message": result.message, "data": result.data}


@router.post("/bills")
def create_bill(
    data: BillCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing", "receptionist")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.create_bill(db, data, issued_by=_user_id(db, current_user))
    return {"message": result.message, "data": result.data}


@router.get("/bills")
def list_bills(
    patient_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing", "receptionist")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.list_bills(db, patient_id=patient_id, status=status, limit=limit)
    return {"message": result.message, "data": result.data}


@router.get("/bills/{bill_id}")
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing", "receptionist")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.get_bill(db, bill_id)
    return {"message": result.message, "data": result.data}


@router.post("/bills/{bill_id}/pay")
def pay_bill(
    bill_id: int,
    data: BillPayRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing", "receptionist")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.mark_paid(db, bill_id, data)
    return {"message": result.message, "data": result.data}


@router.post("/bills/{bill_id}/cancel")
def cancel_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.cancel_bill(db, bill_id)
    return {"message": result.message, "data": result.data}


@router.get("/my/bills")
def my_bills(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("patient", "admin")),
    service: BillingService = Depends(get_billing_service),
):
    """Patient portal — list bills for the logged-in patient."""
    patient_id = current_user.get("patient_id")
    if current_user.get("role") == "patient" and not patient_id:
        from app.exceptions.exceptions import BadRequestException
        raise BadRequestException("No patient profile linked to this account.")
    if current_user.get("role") == "admin" and not patient_id:
        # admin must use the staff list endpoint
        from app.exceptions.exceptions import BadRequestException
        raise BadRequestException("Use /billing/bills for staff access.")
    result = service.list_bills(db, patient_id=int(patient_id))
    return {"message": result.message, "data": result.data}


@router.get("/my/bills/{bill_id}")
def my_bill_detail(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("patient", "admin")),
    service: BillingService = Depends(get_billing_service),
):
    """Patient portal — view one of their own bills (ownership enforced)."""
    patient_id = current_user.get("patient_id")
    result = service.get_bill(db, bill_id)
    bill = result.data
    if not bill:
        from app.exceptions.exceptions import NotFoundException
        raise NotFoundException("Bill not found.")
    if current_user.get("role") == "patient" and int(bill["patient_id"]) != int(patient_id or 0):
        from app.exceptions.exceptions import UnauthorizedException
        raise UnauthorizedException("You can only view your own bills.")
    return {"message": result.message, "data": bill}



@router.get("/service-pricing")
def list_service_pricing(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "billing")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.list_service_pricing(db)
    return {"message": result.message, "data": result.data}


@router.put("/service-pricing/{key}")
def update_service_pricing(
    key: str,
    body: ServicePricingUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
    service: BillingService = Depends(get_billing_service),
):
    result = service.update_service_pricing(
        db, key, body.amount, body.label, body.description
    )
    return {"message": result.message, "data": result.data}
