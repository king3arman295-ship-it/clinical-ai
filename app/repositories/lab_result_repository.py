from sqlalchemy.orm import Session, joinedload
from app.models.lab_result import LabResult
from app.repositories.base_repository import BaseRepository


class LabResultRepository(BaseRepository[LabResult]):

    def __init__(self):
        super().__init__(LabResult)

    def create(self, db: Session, result: LabResult):
        db.add(result)
        db.flush()
        db.refresh(result)
        return result

    def create_many(self, db: Session, results: list[LabResult]):
        db.add_all(results)
        db.flush()
        for r in results:
            db.refresh(r)
        return results

    def get_by_id(self, db: Session, result_id: int):
        return (
            db.query(LabResult)
            .options(joinedload(LabResult.lab_test))
            .filter(LabResult.id == result_id)
            .first()
        )

    def get_by_order(self, db: Session, order_id: int):
        return (
            db.query(LabResult)
            .options(joinedload(LabResult.lab_test))
            .filter(LabResult.lab_order_id == order_id)
            .all()
        )

    def update(self, db: Session, result: LabResult):
        db.add(result)
        db.flush()
        db.refresh(result)
        return result
