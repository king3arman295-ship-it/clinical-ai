from sqlalchemy import Column, Integer, String, Time
from app.core.database import Base


class Clinic(Base):
    __tablename__ = "clinic"

    id = Column(Integer, primary_key=True)

    name = Column(String(150), nullable=False)

    address = Column(String(300))

    phone = Column(String(30))

    whatsapp = Column(String(30))

    email = Column(String(100))

    consultation_fee = Column(String(30))

    opening_time = Column(Time)

    closing_time = Column(Time)