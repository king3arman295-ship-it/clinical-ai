from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.pharmacy_order import PharmacyOrder
from app.models.medication_administration import MedicationAdministration
from app.repositories.base_repository import BaseRepository
from app.common.enums import PharmacyOrderStatus


class PharmacyOrderRepository(BaseRepository[PharmacyOrder]):

    def __init__(self):
        super().__init__(PharmacyOrder)

    def create(self, db: Session, order: PharmacyOrder):
        db.add(order)
        db.flush()
        db.refresh(order)
        return order

    def create_many(self, db: Session, orders: list[PharmacyOrder]):
        db.add_all(orders)
        db.flush()
        for order in orders:
            db.refresh(order)
        return orders

    def get_by_id(self, db: Session, order_id: int):
        return (
            db.query(PharmacyOrder)
            .options(
                joinedload(PharmacyOrder.prescription_item),
                joinedload(PharmacyOrder.medicine),
            )
            .filter(PharmacyOrder.id == order_id)
            .first()
        )

    def get_pending(self, db: Session):
        return (
            db.query(PharmacyOrder)
            .options(
                joinedload(PharmacyOrder.prescription_item),
                joinedload(PharmacyOrder.medicine),
            )
            .filter(PharmacyOrder.status == PharmacyOrderStatus.PENDING.value)
            .order_by(PharmacyOrder.created_at)
            .all()
        )

    def get_out_of_stock_by_medicine(self, db: Session, medicine_id: int):
        return (
            db.query(PharmacyOrder)
            .filter(
                PharmacyOrder.medicine_id == medicine_id,
                PharmacyOrder.status == PharmacyOrderStatus.OUT_OF_STOCK.value,
            )
            .all()
        )

    def get_unlinked_by_medicine_name(self, db: Session, medicine_name: str):
        """Orders whose prescription pre-dates the medicine existing in
        inventory — medicine_id is still NULL. Matched case-insensitively
        against the prescription item's free-text medicine name, since
        that's the only record of what was actually prescribed."""
        from app.models.prescription_item import PrescriptionItem

        return (
            db.query(PharmacyOrder)
            .join(
                PrescriptionItem,
                PharmacyOrder.prescription_item_id == PrescriptionItem.id,
            )
            .filter(
                PharmacyOrder.medicine_id.is_(None),
                PharmacyOrder.status.in_(
                    [
                        PharmacyOrderStatus.PENDING.value,
                        PharmacyOrderStatus.OUT_OF_STOCK.value,
                    ]
                ),
                func.lower(PrescriptionItem.medicine_name)
                == medicine_name.strip().lower(),
            )
            .all()
        )

    def get_by_patient(self, db: Session, patient_id: int):
        return (
            db.query(PharmacyOrder)
            .filter(PharmacyOrder.patient_id == patient_id)
            .order_by(PharmacyOrder.created_at.desc())
            .all()
        )

    def get_by_prescription(self, db: Session, prescription_id: int):
        from app.models.prescription_item import PrescriptionItem

        return (
            db.query(PharmacyOrder)
            .join(
                PrescriptionItem,
                PharmacyOrder.prescription_item_id == PrescriptionItem.id,
            )
            .filter(PrescriptionItem.prescription_id == prescription_id)
            .all()
        )

    def update(self, db: Session, order: PharmacyOrder):
        db.add(order)
        db.flush()
        db.refresh(order)
        return order


class MedicationAdministrationRepository(
    BaseRepository[MedicationAdministration]
):

    def __init__(self):
        super().__init__(MedicationAdministration)

    def create(self, db: Session, record: MedicationAdministration):
        db.add(record)
        db.flush()
        db.refresh(record)
        return record

    def get_by_admission(self, db: Session, admission_id: int):
        return (
            db.query(MedicationAdministration)
            .filter(MedicationAdministration.admission_id == admission_id)
            .order_by(MedicationAdministration.given_at.desc())
            .all()
        )