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
