from sqlalchemy.orm import Session


class UnitOfWork:

    def __init__(self, db: Session):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if exc_type:
            self.db.rollback()
        else:
            self.db.commit()

    def rollback(self):
        self.db.rollback()

    def commit(self):
        self.db.commit()