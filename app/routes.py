from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, APIRouter, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Hospital
from passlib.context import CryptContext
from app.database import SessionLocal, Base, engine
from app import models
from app.auth import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
import datetime, os

from fastapi.security import OAuth2PasswordRequestForm


SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"


SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
from .schemas import DoctorSignupRequest, PatientSignupRequest, LoginRequest

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
Base.metadata.create_all(bind=engine)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/patient/login")

# ---------------------- DB Session ---------------------- #
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------- DOCTOR AUTH ---------------------- #
@router.post("/auth/doctor/signup")
def doctor_signup(payload: DoctorSignupRequest, db: Session = Depends(get_db)):
    if db.query(models.Doctor).filter(models.Doctor.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Doctor already exists")

    doctor = models.Doctor(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        specialization=payload.specialization,
        degree=payload.degree,
        city=payload.city,
        contact=payload.contact,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return {"msg": "Doctor registered", "doctor_id": doctor.id}

@router.post("/auth/doctor/login")
def doctor_login(payload: LoginRequest, db: Session = Depends(get_db)):
    doctor = db.query(models.Doctor).filter(models.Doctor.email == payload.email).first()
    if not doctor or not verify_password(payload.password, doctor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": doctor.email, "role": "doctor"})
    return {
        "token": token,
        "doctor_id": doctor.id,  
        "name": doctor.name       
    }


# ---------------------- PATIENT AUTH ---------------------- #
@router.post("/auth/patient/signup")
@router.post("/patients/signup")  # alias for frontend compatibility
def patient_signup(payload: PatientSignupRequest, db: Session = Depends(get_db)):
    if db.query(models.Patient).filter(models.Patient.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Patient already exists")

    patient = models.Patient(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        city=payload.city,
        age=payload.age,
        gender=payload.gender,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return {"msg": "Patient registered", "patient_id": patient.id}


@router.post("/auth/patient/login")
@router.post("/patients/login")  # alias for frontend compatibility
def patient_login(payload: LoginRequest, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.email == payload.email).first()
    if not patient or not verify_password(payload.password, patient.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": patient.email, "role": "patient"})
    return {"token": token}


# ---------------------- HELPERS ---------------------- #
def get_current_patient(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        patient = db.query(models.Patient).filter(models.Patient.email == email).first()
        if not patient:
            raise HTTPException(status_code=401, detail="Patient not found")
        return patient
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------- DOCTORS ---------------------- #
@router.get("/doctors")
def search_doctors(city: str = None, specialization: str = None, degree: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Doctor)
    if city:
        query = query.filter(models.Doctor.city.ilike(f"%{city}%"))
    if specialization:
        query = query.filter(models.Doctor.specialization.ilike(f"%{specialization}%"))
    if degree:
        query = query.filter(models.Doctor.degree.ilike(f"%{degree}%"))
    return query.all()


# ---------------------- APPOINTMENTS ---------------------- #
@router.post("/appointments")
def book_appointment(doctor_id: int, date: str, time: str, db: Session = Depends(get_db), patient=Depends(get_current_patient)):
    appointment = models.Appointment(
        patient_id=patient.id, doctor_id=doctor_id, date=f"{date} {time}", status="booked"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return {"msg": "Appointment booked", "appointment_id": appointment.id}


@router.get("/appointments")
def get_appointments(db: Session = Depends(get_db), patient=Depends(get_current_patient)):
    return db.query(models.Appointment).filter(models.Appointment.patient_id == patient.id).all()


# ---------------------- PATIENT DETAILS ---------------------- #
@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {
        "id": patient.id,
        "name": patient.name,
        "email": patient.email,
        "city": patient.city,
        "age": patient.age,
        "gender": patient.gender,
    }


# ---------------------- PRESCRIPTIONS ---------------------- #
@router.post("/prescriptions")
def create_prescription(patient: str, medicine: str, db: Session = Depends(get_db)):
    pat = db.query(models.Patient).filter(models.Patient.name.ilike(f"%{patient}%")).first()
    if not pat:
        raise HTTPException(status_code=404, detail="Patient not found")

    # TODO: get doctor_id from token instead of hardcoding
    prescription = models.Prescription(patient_id=pat.id, doctor_id=1, medicine=medicine)
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return {"msg": "Prescription added", "prescription_id": prescription.id}


@router.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db), patient=Depends(get_current_patient)):
    appointment = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id,
        models.Appointment.patient_id == patient.id  # ✅ ensure only their own appt
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    db.delete(appointment)
    db.commit()
    return {"msg": "Appointment cancelled"}




router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/hospital/register")
def register_hospital(name: str, email: str, password: str, city: str, db: Session = Depends(get_db)):
    existing = db.query(Hospital).filter(Hospital.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Hospital already registered")
    
    hashed = pwd_context.hash(password)
    hospital = Hospital(name=name, email=email, password_hash=hashed, city=city)
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return {"message": "Hospital registered successfully", "hospital_id": hospital.id}




@router.post("/auth/hospital/login")
def hospital_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.email == form_data.username).first()
    if not hospital or not pwd_context.verify(form_data.password, hospital.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # JWT Token
    payload = {
        "sub": str(hospital.id),
        "role": "hospital",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "hospital_id": hospital.id}
