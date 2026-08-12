from sqlalchemy.orm import Session

from app.models.ward import Ward
from app.repositories.base_repository import BaseRepository


class WardRepository(BaseRepository[Ward]):

    def __init__(self):
        super().__init__(Ward)

    def get_all(self, db: Session):
        return db.query(Ward).order_by(Ward.name).all()

    def get_by_id(self, db: Session, ward_id: int):
        return db.query(Ward).filter(Ward.id == ward_id).first()

    def update(self, db: Session, ward: Ward):
        db.add(ward)
        db.flush()
        db.refresh(ward)
        return ward

    def delete(self, db: Session, ward: Ward):
        db.delete(ward)
        db.flush()
