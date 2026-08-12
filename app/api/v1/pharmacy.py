from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.auth.dependencies import get_current_user
from app.auth.roles import require_roles

from app.dependencies.services import get_pharmacy_service
from app.services.pharmacy_service import PharmacyService

from app.schemas.pharmacy import (
    MedicineCreate,
    MedicineUpdate,
    MedicineRestock,
    MedicineResponse,
    PharmacyOrderResponse,
    PharmacyOrderDispense,
    MedicationAdministrationCreate,
    MedicationAdministrationResponse,
    WalkInDispenseRequest,
    WalkInSaleResponse,
)

router = APIRouter(
    prefix="/pharmacy",
    tags=["Pharmacy"],
)

PHARMACY_STAFF = ("admin", "pharmacist")


# ═════════════════════════════════════════════════════════════
# Inventory (medicine master list)
# ═════════════════════════════════════════════════════════════
@router.post("/medicines", response_model=MedicineResponse)
def add_medicine(
    medicine: MedicineCreate,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    result = service.add_medicine(db, medicine)
    return result.data


@router.get("/medicines", response_model=list[MedicineResponse])
def list_medicines(
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF, "doctor")),
):
    result = service.get_medicines(db)
    return result.data


@router.get("/medicines/low-stock", response_model=list[MedicineResponse])
def low_stock_medicines(
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    result = service.get_low_stock_medicines(db)
    return result.data


@router.put("/medicines/{medicine_id}", response_model=MedicineResponse)
def update_medicine(
    medicine_id: int,
    medicine: MedicineUpdate,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    result = service.update_medicine(db, medicine_id, medicine)
    return result.data


@router.put("/medicines/{medicine_id}/restock", response_model=MedicineResponse)
def restock_medicine(
    medicine_id: int,
    restock: MedicineRestock,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    result = service.restock_medicine(db, medicine_id, restock)
    return result.data


# ═════════════════════════════════════════════════════════════
# Pharmacy Order Queue (fulfillment half of a prescription)
# ═════════════════════════════════════════════════════════════
@router.get("/orders/pending", response_model=list[PharmacyOrderResponse])
def get_pending_orders(
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    """Pharmacist's incoming queue."""
    result = service.get_pending_orders(db)
    return result.data


@router.get("/orders/me", response_model=list[PharmacyOrderResponse])
def get_my_orders(
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(get_current_user),
):
    """Patient-facing: their own prescribed medicines and whether
    each has been dispensed yet."""
    patient_id = current_user.get("patient_id")
    if not patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")

    result = service.get_orders_for_patient(db, patient_id)
    return result.data


@router.get("/orders/{order_id}", response_model=PharmacyOrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(get_current_user),
):
    result = service.get_order_by_id(db, order_id)
    return result.data


@router.get(
    "/orders/patient/{patient_id}",
    response_model=list[PharmacyOrderResponse],
)
def get_patient_orders(
    patient_id: int,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(get_current_user),
):
    if current_user.get("role") == "patient" and current_user.get("patient_id") != patient_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="You can only view your own orders.")

    result = service.get_orders_for_patient(db, patient_id)
    return result.data


@router.put(
    "/orders/{order_id}/dispense",
    response_model=PharmacyOrderResponse,
)
def dispense_order(
    order_id: int,
    dispense: PharmacyOrderDispense,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    result = service.dispense_order(db, order_id, current_user.get("username"))
    return result.data


# ═════════════════════════════════════════════════════════════
# Medication Administration Record — ongoing IPD dosing
# ═════════════════════════════════════════════════════════════

@router.post("/orders/{order_id}/cancel", response_model=dict)
def cancel_pharmacy_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PHARMACY_STAFF, "admin")),
    service: PharmacyService = Depends(get_pharmacy_service),
):
    """Cancel a pending pharmacy order; notifies doctors and the patient."""
    result = service.cancel_order(
        db,
        order_id,
        cancelled_by_username=current_user.get("username"),
    )
    data = result.data
    # Safety: never leak ORM objects into the JSON response
    if data is not None and not isinstance(data, (dict, list, str, int, float, bool)):
        data = {
            "id": getattr(data, "id", order_id),
            "status": getattr(data, "status", "cancelled"),
            "patient_id": getattr(data, "patient_id", None),
        }
    return {"message": result.message, "data": data}

@router.post(
    "/admissions/{admission_id}/administer",
    response_model=MedicationAdministrationResponse,
)
def log_administration(
    admission_id: int,
    data: MedicationAdministrationCreate,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(
        require_roles(*PHARMACY_STAFF, "doctor")
    ),
):
    result = service.log_administration(
        db, admission_id, current_user.get("username"), data,
    )
    return result.data


@router.get(
    "/admissions/{admission_id}/administrations",
    response_model=list[MedicationAdministrationResponse],
)
def get_administrations(
    admission_id: int,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(get_current_user),
):
    result = service.get_administrations_for_admission(db, admission_id)
    return result.data


# ═════════════════════════════════════════════════════════════
# Walk-in / OTC counter sale (no doctor prescription)
# ═════════════════════════════════════════════════════════════
@router.post("/walk-in", response_model=WalkInSaleResponse)
def walk_in_dispense(
    data: WalkInDispenseRequest,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    """Dispense medicine to a walk-in customer at the pharmacy window."""
    result = service.walk_in_dispense(db, data, current_user.get("username"))
    return result.data


@router.get("/walk-in", response_model=list[WalkInSaleResponse])
def list_walk_in_sales(
    limit: int = 50,
    db: Session = Depends(get_db),
    service: PharmacyService = Depends(get_pharmacy_service),
    current_user=Depends(require_roles(*PHARMACY_STAFF)),
):
    result = service.list_walk_in_sales(db, limit=limit)
    return result.data

