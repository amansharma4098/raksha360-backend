# app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from sqlalchemy.sql import func

# --- Existing models (kept and lightly cleaned) ---

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    specialization = Column(String, nullable=True)
    degree = Column(String, nullable=True)
    city = Column(String, nullable=True)
    contact = Column(String, nullable=True)

    appointments = relationship("Appointment", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")

    def __repr__(self):
        return f"<Doctor(id={self.id}, name={self.name})>"

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    city = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)

    appointments = relationship("Appointment", back_populates="patient")
    prescriptions = relationship("Prescription", back_populates="patient")

    def __repr__(self):
        return f"<Patient(id={self.id}, name={self.name})>"

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String, default="pending")

    doctor = relationship("Doctor", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")

    def __repr__(self):
        return f"<Appointment(id={self.id}, doctor_id={self.doctor_id}, patient_id={self.patient_id}, date={self.date})>"

class Hospital(Base):
    __tablename__ = "hospitals"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    city = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending / active / blocked
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # convenience relationships
    staff = relationship("Staff", back_populates="hospital", cascade="all, delete-orphan")
    pros = relationship("Pro", back_populates="hospital", cascade="all, delete-orphan")
    requests = relationship("HospitalRequest", back_populates="hospital", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Hospital(id={self.id}, name={self.name})>"

# ---- Prescription model (single source of truth) ----
class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True, index=True)

    # integer FKs to fit existing Patient / Doctor
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)

    # raw doctor input
    raw_medicines = Column(JSON, nullable=False)   # list of objects: [{name, dosage, frequency, duration}, ...]
    diagnosis = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # LLM enrichment
    llm_output = Column(JSON, nullable=True)  # {summary, suggested_dosage, warnings, interactions, confidence}
    llm_version = Column(String, nullable=True)
    llm_status = Column(String, nullable=False, default="pending")  # pending/done/error

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # relationships
    patient = relationship("Patient", back_populates="prescriptions", foreign_keys=[patient_id])
    doctor = relationship("Doctor", back_populates="prescriptions", foreign_keys=[doctor_id])

    def __repr__(self):
        return f"<Prescription(id={self.id}, patient_id={self.patient_id}, doctor_id={self.doctor_id}, date={self.created_at})>"

# --- New models for Admin + Hospital Requests + Staff / Pro ---

class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, nullable=False, default="super_admin")  # super_admin / admin / support
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # convenience relationship to requests assigned to this admin
    assigned_requests = relationship("HospitalRequest", back_populates="assigned_admin_user")

    def __repr__(self):
        return f"<AdminUser(id={self.id}, email={self.email})>"

class HospitalRequest(Base):
    __tablename__ = "hospital_requests"
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True, index=True)
    created_by_hospital = Column(Integer, ForeignKey("hospitals.id"), nullable=True)  # optional: who created it
    request_type = Column(String, nullable=False)  # e.g. get_pro, get_doctor, get_staff, onboard_hospital
    payload = Column(JSON, nullable=True)  # flexible JSON payload with fields like {count, location, salary, notes}
    status = Column(String, nullable=False, default="open")  # open / in_progress / resolved / rejected
    assigned_admin = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationships
    hospital = relationship("Hospital", foreign_keys=[hospital_id], back_populates="requests")
    assigned_admin_user = relationship("AdminUser", foreign_keys=[assigned_admin], back_populates="assigned_requests")

    def __repr__(self):
        return f"<HospitalRequest(id={self.id}, hospital_id={self.hospital_id}, type={self.request_type}, status={self.status})>"

class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=True)  # e.g. nurse, cleaner, receptionist
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hospital = relationship("Hospital", back_populates="staff")

    def __repr__(self):
        return f"<Staff(id={self.id}, name={self.name}, hospital_id={self.hospital_id})>"

class Pro(Base):
    __tablename__ = "pros"
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    offered_salary = Column(String, nullable=True)  # keep varchar for flexible formats; change to numeric if needed
    contact = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hospital = relationship("Hospital", back_populates="pros")

    def __repr__(self):
        return f"<Pro(id={self.id}, hospital_id={self.hospital_id}, location={self.location})>"
