from datetime import date, datetime
from pydantic import BaseModel, Field


class NurseBedAssignRequest(BaseModel):
    nurse_user_id: int
    bed_ids: list[int] = Field(min_length=1)


class NurseBedAssignmentResponse(BaseModel):
    id: int
    nurse_user_id: int
    bed_id: int
    is_active: bool
    assigned_at: datetime | None = None
    nurse_username: str | None = None
    ward_name: str | None = None
    bed_number: str | None = None
    patient_name: str | None = None
    admission_id: int | None = None

    class Config:
        from_attributes = True


class CourseItemCreate(BaseModel):
    medicine_id: int | None = None
    medicine_name: str
    # form/type: tablet | syrup | injection | drip | capsule | other
    route: str = "tablet"
    dosage: str
    frequency: str = "OD"
    times_per_day: int | None = None
    schedule_times: str | None = None
    drip_rate: str | None = None
    instructions: str | None = None
    sort_order: int = 0


class MedicationCourseCreate(BaseModel):
    admission_id: int
    ordered_by_doctor_id: int
    title: str = "Ward Medication Course"
    start_date: date
    duration_days: int = Field(default=1, ge=1, le=90)
    clinical_notes: str | None = None
    items: list[CourseItemCreate] = Field(min_length=1)


class MedicationCourseUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    duration_days: int | None = Field(default=None, ge=1, le=90)
    clinical_notes: str | None = None
    items: list[CourseItemCreate] | None = None


class CourseItemResponse(BaseModel):
    id: int
    medicine_id: int | None = None
    medicine_name: str
    route: str
    dosage: str
    frequency: str
    times_per_day: int
    schedule_times: str | None = None
    drip_rate: str | None = None
    instructions: str | None = None
    sort_order: int = 0

    class Config:
        from_attributes = True


class CourseDoseResponse(BaseModel):
    id: int
    course_id: int
    course_item_id: int
    admission_id: int
    scheduled_date: date
    scheduled_time: str | None = None
    status: str
    given_by: int | None = None
    given_at: datetime | None = None
    notes: str | None = None
    medicine_name: str | None = None
    dosage: str | None = None
    route: str | None = None
    drip_rate: str | None = None
    instructions: str | None = None
    patient_name: str | None = None
    bed_label: str | None = None

    class Config:
        from_attributes = True


class MedicationCourseResponse(BaseModel):
    id: int
    admission_id: int
    ordered_by_doctor_id: int
    title: str
    status: str
    start_date: date
    end_date: date | None = None
    duration_days: int
    clinical_notes: str | None = None
    created_at: datetime | None = None
    doctor_name: str | None = None
    patient_name: str | None = None
    bed_label: str | None = None
    items: list[CourseItemResponse] = []
    today_pending: int = 0
    today_given: int = 0

    class Config:
        from_attributes = True


class DoseActionRequest(BaseModel):
    status: str = Field(description="given | held | missed | skipped")
    notes: str | None = None


class NurseDashboardResponse(BaseModel):
    assigned_beds: int = 0
    active_patients: int = 0
    doses_pending_today: int = 0
    doses_given_today: int = 0
    doses_held_today: int = 0
