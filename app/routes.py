from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.database import SessionLocal, Base, engine
from app import models
from app.auth import hash_password, verify_password, create_access_token

Base.metadata.create_all(bind=engine)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/patient/login")  # default, we’ll support doctor too


# DB Session Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------- AUTH ---------------------- #
@router.post("/auth/doctor/signup")
def doctor_signup(name: str, email: str, password: str, specialization: str, degree: str, city: str, contact: str, db: Session = Depends(get_db)):
    if db.query(models.Doctor).filter(models.Doctor.email == email).first():
        raise HTTPException(status_code=400, detail="Doctor already exists")
    doctor = models.Doctor(
        name=name,
        email=email,
        password_hash=hash_password(password),
        specialization=specialization,
        degree=degree,
        city=city,
        contact=contact,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return {"msg": "Doctor registered", "doctor_id": doctor.id}


@router.post("/auth/doctor/login")
def doctor_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    doctor = db.query(models.Doctor).filter(models.Doctor.email == form_data.username).first()
    if not doctor or not verify_password(form_data.password, doctor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": doctor.email, "role": "doctor"})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/auth/patient/signup")
def patient_signup(name: str, email: str, password: str, city: str, age: int, gender: str, db: Session = Depends(get_db)):
    if db.query(models.Patient).filter(models.Patient.email == email).first():
        raise HTTPException(status_code=400, detail="Patient already exists")
    patient = models.Patient(
        name=name,
        email=email,
        password_hash=hash_password(password),
        city=city,
        age=age,
        gender=gender,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return {"msg": "Patient registered", "patient_id": patient.id}


@router.post("/auth/patient/login")
def patient_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.email == form_data.username).first()
    if not patient or not verify_password(form_data.password, patient.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": patient.email, "role": "patient"})
    return {"access_token": token, "token_type": "bearer"}


# ---------------------- DOCTORS ---------------------- #
@router.get("/doctors")
def search_doctors(city: str = None, degree: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Doctor)
    if city:
        query = query.filter(models.Doctor.city.ilike(f"%{city}%"))
    if degree:
        query = query.filter(models.Doctor.degree.ilike(f"%{degree}%"))
    return query.all()


# ---------------------- APPOINTMENTS ---------------------- #
@router.post("/appointments")
def book_appointment(patient_id: int, doctor_id: int, date: str, db: Session = Depends(get_db)):
    appointment = models.Appointment(patient_id=patient_id, doctor_id=doctor_id, date=date, status="booked")
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return {"msg": "Appointment booked", "appointment_id": appointment.id}


@router.get("/appointments")
def get_appointments(patient_id: int = None, doctor_id: int = None, db: Session = Depends(get_db)):
    query = db.query(models.Appointment)
    if patient_id:
        query = query.filter(models.Appointment.patient_id == patient_id)
    if doctor_id:
        query = query.filter(models.Appointment.doctor_id == doctor_id)
    return query.all()
