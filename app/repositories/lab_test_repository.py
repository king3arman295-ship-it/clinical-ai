from sqlalchemy.orm import Session
from app.models.lab_test import LabTest
from app.repositories.base_repository import BaseRepository


class LabTestRepository(BaseRepository[LabTest]):

    def __init__(self):
        super().__init__(LabTest)

    def create(self, db: Session, lab_test: LabTest):
        db.add(lab_test)
        db.flush()
        db.refresh(lab_test)
        return lab_test

    def get_all(self, db: Session, active_only: bool = False):
        q = db.query(LabTest)
        if active_only:
            q = q.filter(LabTest.is_active.is_(True))
        return q.order_by(LabTest.name).all()

    def get_by_id(self, db: Session, test_id: int):
        return db.query(LabTest).filter(LabTest.id == test_id).first()

    def get_by_name(self, db: Session, name: str):
        return db.query(LabTest).filter(LabTest.name.ilike(name.strip())).first()

    def get_by_code(self, db: Session, code: str):
        return db.query(LabTest).filter(LabTest.code.ilike(code.strip())).first()

    def get_by_category(self, db: Session, category: str):
        return (
            db.query(LabTest)
            .filter(LabTest.category == category, LabTest.is_active.is_(True))
            .order_by(LabTest.name)
            .all()
        )

    def update(self, db: Session, lab_test: LabTest):
        db.add(lab_test)
        db.flush()
        db.refresh(lab_test)
        return lab_test
