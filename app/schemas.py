# app/schemas.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime, date

# ---------------- Prescription-related ----------------
class Medicine(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None

class LLMOutput(BaseModel):
    summary: Optional[str] = None
    suggested_dosage: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[str]] = None
    interactions: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None
    raw_text: Optional[str] = None

class PrescriptionCreate(BaseModel):
    patient_id: int
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    raw_medicines: List[Medicine]

class PrescriptionOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    diagnosis: Optional[str]
    notes: Optional[str]
    raw_medicines: List[Medicine]
    llm_output: Optional[LLMOutput]
    llm_status: str
    created_at: datetime

    class Config:
        orm_mode = True

# ---------------- Auth / Signup / Login ----------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class DoctorSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    specialization: Optional[str] = None
    degree: Optional[str] = None
    city: Optional[str] = None
    contact: Optional[str] = None

class PatientSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    city: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None

# ---------------- Appointments ----------------
class AppointmentRequest(BaseModel):
    doctor_id: int
    date: date

# ---------------- Hospital register ----------------
class HospitalRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    city: str

# ---------------- Ticket schemas (single ticket table) ----------------
class TicketCreate(BaseModel):
    """
    Create a ticket with simplified fields:
      - type (category, e.g. "pros" or "staff")
      - count (integer)
      - description (human readable)
    """
    type: str
    count: Optional[int] = None
    description: Optional[str] = None
    hospital_id: Optional[int] = None  # admin-only - ignored for hospital token
    assigned_admin: Optional[int] = None

class TicketUpdate(BaseModel):
    """
    Update a ticket. Fields are optional.
    """
    details: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    count: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assigned_admin: Optional[int] = None
    note: Optional[str] = None  # optional human note (will be stored inside payload.notes or description)

class TicketOut(BaseModel):
    id: int
    hospital_id: Optional[int]
    type: str
    details: Optional[str]
    description: Optional[str]
    count: Optional[int]
    payload: Optional[Dict[str, Any]]
    status: str
    assigned_admin: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    closed_by_admin: Optional[int] = None
    closed_by_hospital: Optional[int] = None

    class Config:
        orm_mode = True



class AdminSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    invite_code: str | None = None  # optional, only if you want invite-based signup