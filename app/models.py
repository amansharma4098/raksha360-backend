from pydantic import BaseModel

from sqlalchemy import Column, Integer, String
from app.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
import datetime
class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # ⚠️ should hash in real-world
    specialization = Column(String, nullable=False)
    city = Column(String, nullable=False)
    contact = Column(String, nullable=True)


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_name = Column(String, nullable=False)
    patient_email = Column(String, nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    date = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="Scheduled")

    doctor = relationship("Doctor", backref="appointments")