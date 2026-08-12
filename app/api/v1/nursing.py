from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.auth.roles import require_roles
from app.auth.dependencies import get_current_user
from app.dependencies.services import get_nursing_service
from app.services.nursing_service import NursingService
from app.schemas.nursing import (
    NurseBedAssignRequest,
    MedicationCourseCreate,
    MedicationCourseUpdate,
    DoseActionRequest,
)

router = APIRouter(prefix="/nursing", tags=["Nursing"])


def _user_id(db: Session, current_user) -> int | None:
    """Prefer JWT id; fall back to username lookup for older tokens."""
    uid = current_user.get("id")
    if uid:
        return int(uid)
    username = current_user.get("username")
    if not username:
        return None
    from app.models.user import User
    user = db.query(User).filter(User.username == username).first()
    return user.id if user else None



@router.get("/nurses")
def list_nurses(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "admission_head")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.list_nurses(db)
    return {"message": result.message, "data": result.data}


@router.post("/assignments")
def assign_beds(
    data: NurseBedAssignRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "admission_head")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.assign_beds(db, data, assigned_by=_user_id(db, current_user))
    return {"message": result.message, "data": result.data}


@router.delete("/assignments/{assignment_id}")
def unassign_bed(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "admission_head")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.unassign_bed(db, assignment_id)
    return {"message": result.message, "data": result.data}


@router.get("/assignments")
def list_assignments(
    nurse_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "admission_head", "nurse")),
    service: NursingService = Depends(get_nursing_service),
):
    role = current_user.get("role")
    if role == "nurse":
        nurse_user_id = _user_id(db, current_user)
    result = service.list_assignments(db, nurse_user_id=nurse_user_id)
    return {"message": result.message, "data": result.data}


@router.get("/dashboard")
def nurse_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("nurse", "admin")),
    service: NursingService = Depends(get_nursing_service),
):
    uid = _user_id(db, current_user)
    result = service.nurse_dashboard(db, uid)
    return {"message": result.message, "data": result.data}


@router.get("/today-doses")
def today_doses(
    day: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("nurse", "admin")),
    service: NursingService = Depends(get_nursing_service),
):
    uid = _user_id(db, current_user)
    result = service.get_today_doses_for_nurse(db, uid, day)
    return {"message": result.message, "data": result.data}


@router.post("/doses/{dose_id}/action")
def act_on_dose(
    dose_id: int,
    data: DoseActionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("nurse", "admin")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.act_on_dose(db, dose_id, data, nurse_user_id=_user_id(db, current_user))
    return {"message": result.message, "data": result.data}


@router.post("/courses")
def create_course(
    data: MedicationCourseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor")),
    service: NursingService = Depends(get_nursing_service),
):
    if current_user.get("role") == "doctor" and current_user.get("doctor_id"):
        data.ordered_by_doctor_id = current_user["doctor_id"]
    result = service.create_course(db, data)
    return {"message": result.message, "data": result.data}


@router.get("/courses/{course_id}")
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor", "nurse", "admission_head")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.get_course(db, course_id)
    return {"message": result.message, "data": result.data}


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int,
    data: MedicationCourseUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.update_course(db, course_id, data)
    return {"message": result.message, "data": result.data}


@router.get("/admissions/{admission_id}/courses")
def list_admission_courses(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor", "nurse", "admission_head", "pharmacist")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.list_courses_for_admission(db, admission_id)
    return {"message": result.message, "data": result.data}


@router.get("/admissions/{admission_id}/doses")
def admission_doses(
    admission_id: int,
    day: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "doctor", "nurse", "admission_head", "pharmacist")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.get_doses_for_admission(db, admission_id, day)
    return {"message": result.message, "data": result.data}


@router.get("/admissions/{admission_id}/compliance")
def admission_compliance(
    admission_id: int,
    day: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "admission_head", "doctor", "nurse", "pharmacist")),
    service: NursingService = Depends(get_nursing_service),
):
    result = service.admission_med_compliance(db, admission_id, day)
    return {"message": result.message, "data": result.data}
