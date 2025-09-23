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
    # date is a date object (your model uses Date). If you want datetime, change type to datetime.
    date: date

# ---------------- Hospital register & ticketing ----------------
class HospitalRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    city: str

class RequestCreateSchema(BaseModel):
    """
    Represents a hospital-created ticket/request.
    payload is flexible — should include fields like:
      { "count": 2, "location": "Delhi", "offered_salary": "15000", "notes": "..." }
    """
    request_type: str
    payload: Dict[str, Any]

class AdminActionSchema(BaseModel):
    """
    Admin actions on tickets:
      action: 'assign' | 'start' | 'resolve' | 'reject' | 'approve_signup'
      assign_to: admin id (int) when action == 'assign'
      note: optional note or reason
    """
    action: str
    assign_to: Optional[int] = None
    note: Optional[str] = None

# ---------------- Request output model ----------------
class RequestOut(BaseModel):
    id: int
    hospital_id: Optional[int]
    request_type: str
    payload: Optional[Dict[str, Any]]
    status: str
    assigned_admin: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
