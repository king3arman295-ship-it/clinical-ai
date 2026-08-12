from sqlalchemy.orm import Session, joinedload
from app.models.lab_order import LabOrder
from app.models.lab_result import LabResult
from app.repositories.base_repository import BaseRepository
from app.common.enums import LabOrderStatus


class LabOrderRepository(BaseRepository[LabOrder]):

    def __init__(self):
        super().__init__(LabOrder)

    def create(self, db: Session, order: LabOrder):
        db.add(order)
        db.flush()
        db.refresh(order)
        return order

    def get_by_id(self, db: Session, order_id: int):
        return (
            db.query(LabOrder)
            .options(
                joinedload(LabOrder.results).joinedload(LabResult.lab_test),
                joinedload(LabOrder.patient),
                joinedload(LabOrder.ordered_by_doctor),
                joinedload(LabOrder.admission),
            )
            .filter(LabOrder.id == order_id)
            .first()
        )

    def get_all(self, db: Session, status: str | None = None, limit: int = 100):
        q = (
            db.query(LabOrder)
            .options(
                joinedload(LabOrder.results).joinedload(LabResult.lab_test),
                joinedload(LabOrder.patient),
                joinedload(LabOrder.ordered_by_doctor),
            )
            .order_by(LabOrder.created_at.desc())
        )
        if status:
            q = q.filter(LabOrder.status == status)
        return q.limit(limit).all()

    def get_by_patient(self, db: Session, patient_id: int):
        return (
            db.query(LabOrder)
            .options(joinedload(LabOrder.results).joinedload(LabResult.lab_test))
            .filter(LabOrder.patient_id == patient_id)
            .order_by(LabOrder.created_at.desc())
            .all()
        )

    def get_pending_queue(self, db: Session):
        return (
            db.query(LabOrder)
            .options(
                joinedload(LabOrder.results).joinedload(LabResult.lab_test),
                joinedload(LabOrder.patient),
                joinedload(LabOrder.ordered_by_doctor),
            )
            .filter(
                LabOrder.status.in_([
                    LabOrderStatus.PENDING.value,
                    LabOrderStatus.SAMPLE_COLLECTED.value,
                    LabOrderStatus.PROCESSING.value,
                ])
            )
            .order_by(LabOrder.created_at.asc())
            .all()
        )

    def update(self, db: Session, order: LabOrder):
        db.add(order)
        db.flush()
        db.refresh(order)
        return order
