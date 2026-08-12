from sqlalchemy.orm import Session, joinedload

from app.models.bed import Bed
from app.repositories.base_repository import BaseRepository
from app.common.enums import BedStatus


class BedRepository(BaseRepository[Bed]):

    def __init__(self):
        super().__init__(Bed)

    def get_all(self, db: Session):
        return (
            db.query(Bed)
            .options(joinedload(Bed.ward))
            .order_by(Bed.ward_id, Bed.bed_number)
            .all()
        )

    def get_by_id(self, db: Session, bed_id: int):
        return db.query(Bed).filter(Bed.id == bed_id).first()

    def get_by_ward(self, db: Session, ward_id: int):
        return (
            db.query(Bed)
            .options(joinedload(Bed.ward))
            .filter(Bed.ward_id == ward_id)
            .order_by(Bed.bed_number)
            .all()
        )

    def get_vacant_beds(self, db: Session, ward_id: int | None = None):
        query = db.query(Bed).filter(Bed.status == BedStatus.VACANT.value)
        if ward_id:
            query = query.filter(Bed.ward_id == ward_id)
        return query.all()

    def update(self, db: Session, bed: Bed):
        db.add(bed)
        db.flush()
        db.refresh(bed)
        return bed

    def delete(self, db: Session, bed: Bed):
        db.delete(bed)
        db.flush()
