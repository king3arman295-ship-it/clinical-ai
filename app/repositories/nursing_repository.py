from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.repositories.base_repository import BaseRepository
from app.models.nurse_bed_assignment import NurseBedAssignment
from app.models.medication_course import (
    MedicationCourse,
    MedicationCourseItem,
    MedicationCourseDose,
)


class NurseBedAssignmentRepository(BaseRepository[NurseBedAssignment]):
    def __init__(self):
        super().__init__(NurseBedAssignment)

    def get_active_by_nurse(self, db: Session, nurse_user_id: int):
        return (
            db.query(NurseBedAssignment)
            .options(joinedload(NurseBedAssignment.bed))
            .filter(
                NurseBedAssignment.nurse_user_id == nurse_user_id,
                NurseBedAssignment.is_active.is_(True),
            )
            .all()
        )

    def get_active_by_bed(self, db: Session, bed_id: int):
        return (
            db.query(NurseBedAssignment)
            .filter(
                NurseBedAssignment.bed_id == bed_id,
                NurseBedAssignment.is_active.is_(True),
            )
            .all()
        )

    def get_all_active(self, db: Session):
        return (
            db.query(NurseBedAssignment)
            .options(
                joinedload(NurseBedAssignment.bed),
                joinedload(NurseBedAssignment.nurse),
            )
            .filter(NurseBedAssignment.is_active.is_(True))
            .all()
        )

    def deactivate(self, db: Session, assignment_id: int):
        obj = self.get_by_id(db, assignment_id)
        if obj:
            obj.is_active = False
            db.flush()
        return obj


class MedicationCourseRepository(BaseRepository[MedicationCourse]):
    def __init__(self):
        super().__init__(MedicationCourse)

    def get_by_id_full(self, db: Session, course_id: int):
        return (
            db.query(MedicationCourse)
            .options(
                joinedload(MedicationCourse.items),
                joinedload(MedicationCourse.admission),
                joinedload(MedicationCourse.admission),
                joinedload(MedicationCourse.ordered_by_doctor),
            )
            .filter(MedicationCourse.id == course_id)
            .first()
        )

    def get_by_admission(self, db: Session, admission_id: int):
        return (
            db.query(MedicationCourse)
            .options(joinedload(MedicationCourse.items))
            .filter(MedicationCourse.admission_id == admission_id)
            .order_by(MedicationCourse.created_at.desc())
            .all()
        )

    def get_active_by_admission(self, db: Session, admission_id: int):
        return (
            db.query(MedicationCourse)
            .options(joinedload(MedicationCourse.items))
            .filter(
                MedicationCourse.admission_id == admission_id,
                MedicationCourse.status == "active",
            )
            .all()
        )


class MedicationCourseItemRepository(BaseRepository[MedicationCourseItem]):
    def __init__(self):
        super().__init__(MedicationCourseItem)


class MedicationCourseDoseRepository(BaseRepository[MedicationCourseDose]):
    def __init__(self):
        super().__init__(MedicationCourseDose)

    def get_by_id(self, db: Session, obj_id: int):
        """Load dose with item + admission so act_on_dose / enrich never lazy-load after commit."""
        return (
            db.query(MedicationCourseDose)
            .options(
                joinedload(MedicationCourseDose.item),
                joinedload(MedicationCourseDose.admission),
            )
            .filter(MedicationCourseDose.id == obj_id)
            .first()
        )

    def get_for_date_admission(self, db: Session, admission_id: int, day: date):
        return (
            db.query(MedicationCourseDose)
            .options(
                joinedload(MedicationCourseDose.item),
                joinedload(MedicationCourseDose.admission),
                joinedload(MedicationCourseDose.admission),
            )
            .filter(
                MedicationCourseDose.admission_id == admission_id,
                MedicationCourseDose.scheduled_date == day,
            )
            .order_by(MedicationCourseDose.scheduled_time)
            .all()
        )

    def get_for_date_beds(self, db: Session, bed_ids: list[int], day: date):
        from app.models.admission import Admission
        from app.common.enums import AdmissionStatus

        return (
            db.query(MedicationCourseDose)
            .join(Admission, Admission.id == MedicationCourseDose.admission_id)
            .options(
                joinedload(MedicationCourseDose.item),
                joinedload(MedicationCourseDose.admission),
                joinedload(MedicationCourseDose.admission),
            )
            .filter(
                MedicationCourseDose.scheduled_date == day,
                Admission.bed_id.in_(bed_ids),
                Admission.status == AdmissionStatus.ADMITTED.value,
            )
            .order_by(MedicationCourseDose.scheduled_time)
            .all()
        )

    def count_by_status_date_beds(self, db: Session, bed_ids: list[int], day: date, status: str):
        from app.models.admission import Admission
        from app.common.enums import AdmissionStatus

        return (
            db.query(MedicationCourseDose)
            .join(Admission, Admission.id == MedicationCourseDose.admission_id)
            .filter(
                MedicationCourseDose.scheduled_date == day,
                MedicationCourseDose.status == status,
                Admission.bed_id.in_(bed_ids),
                Admission.status == AdmissionStatus.ADMITTED.value,
            )
            .count()
        )
