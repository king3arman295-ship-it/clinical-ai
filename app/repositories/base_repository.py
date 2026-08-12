from typing import Generic, TypeVar, Type

from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):

    def __init__(self, model: Type[T]):
        self.model = model

    def create(self, db: Session, obj: T):

        db.add(obj)
        db.flush()
        db.refresh(obj)

        return obj

    def get_by_id(self, db: Session, obj_id: int):

        return (
            db.query(self.model)
            .filter(self.model.id == obj_id)
            .first()
        )

    def get_all(self, db: Session):

        return db.query(self.model).all()

    def update(self, db: Session, obj):

        db.flush()
        db.refresh(obj)

        return obj

    def delete(self, db: Session, obj):

        db.delete(obj)