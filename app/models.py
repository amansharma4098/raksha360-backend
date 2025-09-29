# app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from sqlalchemy.sql import func
from datetime import datetime

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True, index=True)
    hospital = relationship("Hospital", back_populates="doctors", foreign_keys=[hospital_id])

    appointments = relationship("Appointment", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")

    def __repr__(self):
        return f"<Doctor(id={self.id}, name={self.name}, hospital_id={self.hospital_id})>"


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    city = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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

    staff = relationship("Staff", back_populates="hospital", cascade="all, delete-orphan")
    pros = relationship("Pro", back_populates="hospital", cascade="all, delete-orphan")

    # Tickets relationship (single ticket table).
    # Must specify foreign_keys because Ticket has multiple FKs that reference hospitals.id
    tickets = relationship(
        "Ticket",
        back_populates="hospital",
        cascade="all, delete-orphan",
        foreign_keys="Ticket.hospital_id"  # explicit disambiguation
    )

    doctors = relationship("Doctor", back_populates="hospital", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Hospital(id={self.id}, name={self.name})>"


class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True, index=True)

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)

    raw_medicines = Column(JSON, nullable=False)
    diagnosis = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    llm_output = Column(JSON, nullable=True)
    llm_version = Column(String, nullable=True)
    llm_status = Column(String, nullable=False, default="pending")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="prescriptions", foreign_keys=[patient_id])
    doctor = relationship("Doctor", back_populates="prescriptions", foreign_keys=[doctor_id])

    def __repr__(self):
        return f"<Prescription(id={self.id}, patient_id={self.patient_id}, doctor_id={self.doctor_id}, date={self.created_at})>"


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, nullable=False, default="super_admin")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # convenience relationship to tickets assigned to this admin
    assigned_tickets = relationship(
        "Ticket",
        back_populates="assigned_admin_user",
        foreign_keys="Ticket.assigned_admin"
    )

    def __repr__(self):
        return f"<AdminUser(id={self.id}, email={self.email})>"


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=True)
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
    offered_salary = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hospital = relationship("Hospital", back_populates="pros")

    def __repr__(self):
        return f"<Pro(id={self.id}, hospital_id={self.hospital_id}, location={self.location})>"


class Ticket(Base):
    """
    Central ticket table for both hospital and admin workflows.
    Only this table is used for ticketing now.
    """
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True, index=True)  # which hospital this ticket belongs to
    type = Column(String, nullable=False)           # e.g. get_staff, get_pro, onboard_hospital
    details = Column(Text, nullable=True)           # human readable details
    payload = Column(JSON, nullable=True)           # structured JSON payload
    status = Column(String, nullable=False, default="open")   # open / in_progress / resolved / rejected / closed
    assigned_admin = Column(Integer, ForeignKey("admin_users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # who closed it (mutually exclusive-ish: either admin closed or hospital closed)
    closed_by_admin = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    closed_by_hospital = Column(Integer, ForeignKey("hospitals.id"), nullable=True)

    # last updater tracking
    last_updated_by_admin = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    last_updated_by_hospital = Column(Integer, ForeignKey("hospitals.id"), nullable=True)

    # relationships
    # explicit foreign_keys on relationship below disambiguates join condition
    hospital = relationship("Hospital", back_populates="tickets", foreign_keys=[hospital_id])
    assigned_admin_user = relationship("AdminUser", foreign_keys=[assigned_admin], back_populates="assigned_tickets")
    closed_by_admin_user = relationship("AdminUser", foreign_keys=[closed_by_admin], viewonly=True)
    last_updated_admin_user = relationship("AdminUser", foreign_keys=[last_updated_by_admin], viewonly=True)

    def __repr__(self):
        return f"<Ticket(id={self.id}, hospital_id={self.hospital_id}, type={self.type}, status={self.status})>"
