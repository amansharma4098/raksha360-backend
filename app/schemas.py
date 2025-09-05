from pydantic import BaseModel

# ---------------- Doctor ---------------- #
class DoctorSignupRequest(BaseModel):
    name: str
    email: str
    password: str
    specialization: str
    degree: str
    city: str
    contact: str


# ---------------- Patient ---------------- #
class PatientSignupRequest(BaseModel):
    name: str
    email: str
    password: str
    city: str
    age: int
    gender: str


# ---------------- Common ---------------- #
class LoginRequest(BaseModel):
    email: str
    password: str


class AppointmentRequest(BaseModel):
    doctor_id: int
    date: str   # could be `datetime.date` if you want stricter typing
    time: str   # or `datetime.time`


class PrescriptionRequest(BaseModel):
    patient: str  # or patient_id if you prefer IDs
    medicine: str


class HospitalRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    city: str


