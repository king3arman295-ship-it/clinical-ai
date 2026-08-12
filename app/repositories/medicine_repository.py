from sqlalchemy.orm import Session

from app.models.medicine import Medicine
from app.repositories.base_repository import BaseRepository


class MedicineRepository(BaseRepository[Medicine]):

    def __init__(self):
        super().__init__(Medicine)

    def create(self, db: Session, medicine: Medicine):
        db.add(medicine)
        db.flush()
        db.refresh(medicine)
        return medicine

    def get_all(self, db: Session):
        return db.query(Medicine).order_by(Medicine.name).all()

    def get_by_id(self, db: Session, medicine_id: int):
        return db.query(Medicine).filter(Medicine.id == medicine_id).first()

    def get_by_name(self, db: Session, name: str):
        return (
            db.query(Medicine)
            .filter(Medicine.name.ilike(name.strip()))
            .first()
        )

    def get_by_name_form_dosage(self, db: Session, name: str, form: str | None = None, dosage: str | None = None):
        q = db.query(Medicine).filter(Medicine.name.ilike((name or "").strip()))
        if form:
            q = q.filter(Medicine.form.ilike(str(form).strip().lower()))
        rows = q.all()
        if not rows:
            return None
        if dosage:
            d = str(dosage).strip().lower()
            exact = [r for r in rows if (getattr(r, "dosage", None) or "").strip().lower() == d]
            if exact:
                return exact[0]
            soft = [r for r in rows if d and d in (getattr(r, "dosage", None) or "").strip().lower()]
            if soft:
                return soft[0]
        return rows[0]

    def get_low_stock(self, db: Session):
        return (
            db.query(Medicine)
            .filter(Medicine.stock_qty <= Medicine.reorder_threshold)
            .all()
        )

    def update(self, db: Session, medicine: Medicine):
        db.add(medicine)
        db.flush()
        db.refresh(medicine)
        return medicine
