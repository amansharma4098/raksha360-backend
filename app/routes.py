from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models
from app.database import SessionLocal
from datetime import datetime
from app.models import Appointment, Doctor
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. Doctor Signup
@router.post("/doctors/signup")
def signup_doctor(name: str, email: str, password: str, specialization: str, city: str, contact: str, db: Session = Depends(get_db)):
    doctor = models.Doctor(
        name=name,
        email=email,
        password=password,  # ⚠️ hash later
        specialization=specialization,
        city=city,
        contact=contact,
    )
    db.add(doctor)
    try:
        db.commit()
        db.refresh(doctor)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    return {"message": "Doctor registered successfully", "doctor": doctor.id}

# 2. Update Doctor Info
@router.put("/doctors/{doctor_id}")
def update_doctor(doctor_id: int, specialization: str = None, city: str = None, contact: str = None, db: Session = Depends(get_db)):
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if specialization:
        doctor.specialization = specialization
    if city:
        doctor.city = city
    if contact:
        doctor.contact = contact

    db.commit()
    db.refresh(doctor)
    return {"message": "Doctor updated", "doctor": doctor}

# 3. Get Doctors by City
@router.get("/doctors")
def get_doctors(city: str, db: Session = Depends(get_db)):
    doctors = db.query(models.Doctor).filter(models.Doctor.city.ilike(city)).all()
    return doctors




# Book Appointment
@router.post("/appointments")
def book_appointment(
    patient_name: str,
    patient_email: str,
    doctor_id: int,
    date: str,  # frontend will pass ISO string
    db: Session = Depends(get_db),
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    appointment = Appointment(
        patient_name=patient_name,
        patient_email=patient_email,
        doctor_id=doctor_id,
        date=datetime.fromisoformat(date),
        status="Scheduled",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return {"message": "Appointment booked", "appointment_id": appointment.id}

# Get Appointments for a Patient
@router.get("/appointments")
def get_appointments(patient_email: str, db: Session = Depends(get_db)):
    appointments = db.query(Appointment).filter(Appointment.patient_email == patient_email).all()
    return appointments

# Get Appointments for a Doctor
@router.get("/doctors/{doctor_id}/appointments")
def get_doctor_appointments(doctor_id: int, db: Session = Depends(get_db)):
    appointments = db.query(Appointment).filter(Appointment.doctor_id == doctor_id).all()
    return appointments