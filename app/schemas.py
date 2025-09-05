from pydantic import BaseModel, EmailStr
from datetime import date, time

# ---------------- Doctor ---------------- #
class DoctorSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    specialization: str
    degree: str
    city: str
    contact: str

# ---------------- Patient ---------------- #
class PatientSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    city: str
    age: int
    gender: str

# ---------------- Common ---------------- #
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AppointmentRequest(BaseModel):
    doctor_id: int
    date: date      # expects YYYY-MM-DD format input, auto-parsed to datetime.date
    time: time      # expects HH:MM[:SS] format input, auto-parsed to datetime.time

class PrescriptionRequest(BaseModel):
    patient_id: int   # use ID to uniquely identify patient
    medicine: str

class HospitalRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    city: str
