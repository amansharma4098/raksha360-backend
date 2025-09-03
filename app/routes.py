from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.database import SessionLocal, Base, engine
from app import models
from app.auth import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM

from .schemas import DoctorSignupRequest, PatientSignupRequest, LoginRequest

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
    return {"token": token}


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
