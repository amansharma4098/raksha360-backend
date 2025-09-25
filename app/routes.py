# app/router.py
from fastapi import APIRouter, Depends, HTTPException, Response, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
import traceback
import os

from app.database import SessionLocal, Base, engine, get_db
from app import models
from app.schemas import (
    DoctorSignupRequest, PatientSignupRequest, LoginRequest,
    AppointmentRequest, PrescriptionCreate, PrescriptionOut,
    HospitalRegisterRequest, RequestCreateSchema, AdminActionSchema
)
from app.auth import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM

# LangChain + PDF utils (ensure these files exist)
from .langchain_agent import call_langchain_agent
from .utils.pdf import generate_prescription_pdf
# ensure tables (dev). In production use Alembic migrations.
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 schemes (tokenUrl must match your login endpoints)
oauth2_scheme_patient = OAuth2PasswordBearer(tokenUrl="auth/patient/login")
oauth2_scheme_doctor = OAuth2PasswordBearer(tokenUrl="auth/doctor/login")
oauth2_scheme_generic = OAuth2PasswordBearer(tokenUrl="auth/patient/login")  # for endpoints where token role may vary
oauth2_scheme_hospital = OAuth2PasswordBearer(tokenUrl="auth/hospital/login")
oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="auth/admin/login")

# ---------------------- AUTH HELPERS ---------------------- #
def decode_token_payload(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_patient(token: str = Depends(oauth2_scheme_patient), db: Session = Depends(get_db)):
    """
    Returns Patient model instance based on token 'sub' (email).
    """
    try:
        payload = decode_token_payload(token)
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        patient = db.query(models.Patient).filter(models.Patient.email == email).first()
        if not patient:
            raise HTTPException(status_code=401, detail="Patient not found")
        return patient
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_doctor(token: str = Depends(oauth2_scheme_doctor), db: Session = Depends(get_db)):
    """
    Returns Doctor model instance based on token 'sub' (email).
    """
    try:
        payload = decode_token_payload(token)
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        doctor = db.query(models.Doctor).filter(models.Doctor.email == email).first()
        if not doctor:
            raise HTTPException(status_code=401, detail="Doctor not found")
        return doctor
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_hospital(token: str = Depends(oauth2_scheme_hospital), db: Session = Depends(get_db)):
    """
    Returns Hospital model instance based on token 'sub' (email).
    """
    try:
        payload = decode_token_payload(token)
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        hospital = db.query(models.Hospital).filter(models.Hospital.email == email).first()
        if not hospital:
            raise HTTPException(status_code=401, detail="Hospital not found")
        return hospital
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_admin(token: str = Depends(oauth2_scheme_admin), db: Session = Depends(get_db)):
    """
    Returns AdminUser model instance based on token 'sub' (email).
    """
    try:
        payload = decode_token_payload(token)
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        admin = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return admin
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------- PATIENT AUTH ---------------------- #
@router.post("/auth/patient/signup")
@router.post("/patients/signup")
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
@router.post("/patients/login")
def patient_login(payload: LoginRequest, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.email == payload.email).first()
    if not patient:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    verified = verify_password(payload.password, patient.password_hash)
    if not verified:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": patient.email, "role": "patient", "id": patient.id})
    return {"token": token}

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
    token = create_access_token({"sub": doctor.email, "role": "doctor", "id": doctor.id})
    return {
        "token": token,
        "doctor_id": doctor.id,
        "name": doctor.name
    }

# ---------------------- DOCTORS SEARCH ---------------------- #
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
def book_appointment(payload: AppointmentRequest, db: Session = Depends(get_db), patient: models.Patient = Depends(get_current_patient)):
    appointment = models.Appointment(
        patient_id=patient.id,
        doctor_id=payload.doctor_id,
        date=payload.date,
        status="booked"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return {"msg": "Appointment booked", "appointment_id": appointment.id}

@router.get("/appointments")
def get_appointments(db: Session = Depends(get_db), patient: models.Patient = Depends(get_current_patient)):
    return db.query(models.Appointment).filter(models.Appointment.patient_id == patient.id).all()

@router.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db), patient: models.Patient = Depends(get_current_patient)):
    appointment = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id,
        models.Appointment.patient_id == patient.id
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    db.delete(appointment)
    db.commit()
    return {"msg": "Appointment cancelled"}

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

# ---------------------- PRESCRIPTIONS (LangChain-enabled) ---------------------- #
@router.post("/prescriptions", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
def create_prescription(pres_in: PrescriptionCreate, db: Session = Depends(get_db), current_doctor: models.Doctor = Depends(get_current_doctor)):
    pres = models.Prescription(
        patient_id=pres_in.patient_id,
        doctor_id=current_doctor.id,
        raw_medicines=[m.dict() for m in pres_in.raw_medicines],
        diagnosis=pres_in.diagnosis,
        notes=pres_in.notes,
        llm_status="pending"
    )
    db.add(pres)
    db.commit()
    db.refresh(pres)

    patient = db.query(models.Patient).filter(models.Patient.id == pres.patient_id).first()
    patient_name = patient.name if patient else f"id:{pres.patient_id}"

    try:
        llm_result = call_langchain_agent(patient_name, pres.patient_id, pres.diagnosis or "", pres.raw_medicines)
        pres.llm_output = llm_result
        pres.llm_version = llm_result.get("_meta_model", "langchain") if isinstance(llm_result, dict) else "langchain"
        pres.llm_status = "done"
    except Exception as e:
        pres.llm_output = {"error": str(e), "traceback": traceback.format_exc()}
        pres.llm_status = "error"

    db.add(pres)
    db.commit()
    db.refresh(pres)
    return pres

@router.get("/prescriptions/patient/{patient_id}", response_model=list[PrescriptionOut])
def list_patient_prescriptions(patient_id: int, token: str = Depends(oauth2_scheme_generic), db: Session = Depends(get_db)):
    payload = decode_token_payload(token)
    role = payload.get("role")
    sub = payload.get("sub")

    if role == "patient":
        patient = db.query(models.Patient).filter(models.Patient.email == sub).first()
        if not patient or patient.id != patient_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif role == "doctor":
        doctor = db.query(models.Doctor).filter(models.Doctor.email == sub).first()
        if not doctor:
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = db.query(models.Prescription).filter(models.Prescription.patient_id == patient_id).order_by(models.Prescription.created_at.desc()).all()
    return items

@router.get("/prescriptions/{pres_id}", response_model=PrescriptionOut)
def get_prescription(pres_id: int, token: str = Depends(oauth2_scheme_generic), db: Session = Depends(get_db)):
    pres = db.query(models.Prescription).filter(models.Prescription.id == pres_id).first()
    if not pres:
        raise HTTPException(status_code=404, detail="Prescription not found")

    payload = decode_token_payload(token)
    role = payload.get("role")
    sub = payload.get("sub")

    if role == "patient":
        patient = db.query(models.Patient).filter(models.Patient.email == sub).first()
        if not patient or patient.id != pres.patient_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif role == "doctor":
        doctor = db.query(models.Doctor).filter(models.Doctor.email == sub).first()
        if not doctor or doctor.id != pres.doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    return pres

@router.get("/prescriptions/{pres_id}/download")
def download_prescription_pdf(pres_id: int, token: str = Depends(oauth2_scheme_generic), db: Session = Depends(get_db)):
    pres = db.query(models.Prescription).filter(models.Prescription.id == pres_id).first()
    if not pres:
        raise HTTPException(status_code=404, detail="Prescription not found")

    payload = decode_token_payload(token)
    role = payload.get("role")
    sub = payload.get("sub")

    authorized = False
    if role == "patient":
        patient = db.query(models.Patient).filter(models.Patient.email == sub).first()
        if patient and patient.id == pres.patient_id:
            authorized = True
    elif role == "doctor":
        doctor = db.query(models.Doctor).filter(models.Doctor.email == sub).first()
        if doctor and doctor.id == pres.doctor_id:
            authorized = True
    elif role in ("admin", "hospital"):
        authorized = True

    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized")

    pres_dict = {
        "id": pres.id,
        "patient_id": pres.patient_id,
        "doctor_id": pres.doctor_id,
        "diagnosis": pres.diagnosis,
        "raw_medicines": pres.raw_medicines,
        "llm_output": pres.llm_output,
        "created_at": pres.created_at
    }
    pdf_bytes = generate_prescription_pdf(pres_dict)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="prescription_{pres.id}.pdf"'
    })

# ---------------------- HOSPITAL AUTH & ONBOARD (Hospital portal) ---------------------- #
# JSON-based registration (preferred)
@router.post("/hospital/register")
def register_hospital(payload: HospitalRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.Hospital).filter(models.Hospital.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Hospital already registered")
    hashed = hash_password(payload.password)
    hospital = models.Hospital(
        name=payload.name,
        email=payload.email,
        password_hash=hashed,
        city=payload.city,
        status="pending"
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    # Optionally create a "signup" ticket for admin review
    signup_ticket = models.HospitalRequest(
        hospital_id=hospital.id,
        created_by_hospital=None,
        request_type="onboard_hospital",
        payload={"name": payload.name, "email": payload.email, "city": payload.city},
        status="open"
    )
    db.add(signup_ticket)
    db.commit()
    return {"message": "Hospital registered and signup request submitted", "hospital_id": hospital.id}

# Form-based registration (for HTML forms / curl --data)
@router.post("/hospital/register-form")
def register_hospital_form(
    name: str = Form(...),
    email: str = Form(...),
    city: str = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(models.Hospital).filter(models.Hospital.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Hospital already registered")
    hashed = hash_password(password)
    hospital = models.Hospital(
        name=name,
        email=email,
        password_hash=hashed,
        city=city or "",
        status="pending"
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    signup_ticket = models.HospitalRequest(
        hospital_id=hospital.id,
        created_by_hospital=None,
        request_type="onboard_hospital",
        payload={"name": name, "email": email, "city": city},
        status="open"
    )
    db.add(signup_ticket)
    db.commit()
    return {"message": "Hospital registered and signup request submitted", "hospital_id": hospital.id}

@router.post("/auth/hospital/login")
def hospital_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    hospital = db.query(models.Hospital).filter(models.Hospital.email == form_data.username).first()
    if not hospital or not verify_password(form_data.password, hospital.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    payload = {
        "sub": str(hospital.email),
        "role": "hospital",
        "hospital_id": str(hospital.id),
        "exp": datetime.utcnow() + timedelta(hours=12)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "hospital_id": hospital.id}

# ---------------------- HOSPITAL REQUESTS (Tickets) ---------------------- #
@router.post("/hospital/requests")
def create_hospital_request(payload: RequestCreateSchema, hospital: models.Hospital = Depends(get_current_hospital), db: Session = Depends(get_db)):
    """
    Hospital creates a ticket/request (e.g. get_pro, get_doctor, get_staff).
    payload should include fields such as count, location, offered_salary, additional_notes.
    """
    ticket = models.HospitalRequest(
        hospital_id=hospital.id,
        created_by_hospital=None,
        request_type=payload.request_type,
        payload=payload.payload,
        status="open"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"msg": "Request created", "request_id": ticket.id}

@router.get("/hospital/requests")
def list_hospital_requests(hospital: models.Hospital = Depends(get_current_hospital), db: Session = Depends(get_db)):
    rows = db.query(models.HospitalRequest).filter(models.HospitalRequest.hospital_id == hospital.id).order_by(models.HospitalRequest.created_at.desc()).all()
    return rows

@router.get("/hospital/dashboard")
def hospital_dashboard(hospital: models.Hospital = Depends(get_current_hospital), db: Session = Depends(get_db)):
    # provide the card counts (staff/doctors/pros) - adjust field names as needed
    staff_count = db.query(models.Staff).filter(models.Staff.hospital_id == hospital.id).count() if hasattr(models, "Staff") else 0
    doctor_count = db.query(models.Doctor).filter(models.Doctor.hospital_id == hospital.id).count() if hasattr(models, "Doctor") else 0
    pro_count = db.query(models.Pro).filter(models.Pro.hospital_id == hospital.id).count() if hasattr(models, "Pro") else 0
    req_count = db.query(models.HospitalRequest).filter(models.HospitalRequest.hospital_id == hospital.id).count()
    return {
        "staff_count": staff_count,
        "doctor_count": doctor_count,
        "pro_count": pro_count,
        "request_count": req_count
    }

# ---------------------- ADMIN AUTH & ADMIN PORTAL ---------------------- #
@router.post("/auth/admin/login")
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(models.AdminUser).filter(models.AdminUser.email == payload.email).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    token = create_access_token({"sub": admin.email, "role": "admin", "id": admin.id})
    return {"token": token, "admin_id": admin.id, "name": admin.name}

@router.get("/admin/requests")
def admin_list_requests(status: str = None, current_admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    q = db.query(models.HospitalRequest)
    if status:
        q = q.filter(models.HospitalRequest.status == status)
    rows = q.order_by(models.HospitalRequest.created_at.desc()).all()
    return rows

@router.get("/admin/requests/{request_id}")
def admin_get_request(request_id: str, current_admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    r = db.query(models.HospitalRequest).filter(models.HospitalRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    return r

@router.post("/admin/requests/{request_id}/action")
def admin_take_action(request_id: str, action: AdminActionSchema, current_admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    action.action: assign/start/resolve/reject/approve_signup
    action.assign_to: admin id to assign
    """
    r = db.query(models.HospitalRequest).filter(models.HospitalRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Not found")

    if action.action == "assign" and action.assign_to:
        r.assigned_admin = action.assign_to
        r.status = "in_progress"
    elif action.action == "start":
        r.status = "in_progress"
    elif action.action == "resolve":
        r.status = "resolved"
    elif action.action == "reject":
        r.status = "rejected"
    elif action.action == "approve_signup":
        # approve hospital signup flow: set hospital.status = 'active'
        hosp = db.query(models.Hospital).filter(models.Hospital.id == r.hospital_id).first()
        if hosp:
            hosp.status = "active"
            r.status = "resolved"
            db.add(hosp)
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    db.add(r)
    db.commit()
    db.refresh(r)
    return {"msg": "Action applied", "request": r}

@router.post("/admin/hospitals")
def admin_create_hospital(h: HospitalRegisterRequest, current_admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    existing = db.query(models.Hospital).filter(models.Hospital.email == h.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Hospital already exists")
    hashed = hash_password(h.password)
    new = models.Hospital(name=h.name, email=h.email, password_hash=hashed, city=h.city, status="active")
    db.add(new)
    db.commit()
    db.refresh(new)
    return {"msg": "Hospital created", "hospital_id": new.id}

# End of file
