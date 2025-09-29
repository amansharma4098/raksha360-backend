# app/router.py
from fastapi import APIRouter, Depends, HTTPException, Response, status, Form, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import traceback
import logging
import sys

from app.database import SessionLocal, Base, engine, get_db
from app import models
from app.schemas import (
    DoctorSignupRequest, PatientSignupRequest, LoginRequest,
    AppointmentRequest, PrescriptionCreate, PrescriptionOut,
    HospitalRegisterRequest, TicketCreate, TicketUpdate, TicketOut
)
from app.auth import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from .langchain_agent import call_langchain_agent
from .utils.pdf import generate_prescription_pdf

Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = logging.getLogger("uvicorn.error")

# OAuth2 schemes
oauth2_scheme_patient = OAuth2PasswordBearer(tokenUrl="auth/patient/login")
oauth2_scheme_doctor = OAuth2PasswordBearer(tokenUrl="auth/doctor/login")
oauth2_scheme_generic = OAuth2PasswordBearer(tokenUrl="auth/patient/login")
oauth2_scheme_hospital = OAuth2PasswordBearer(tokenUrl="auth/hospital/login")
oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="auth/admin/login")

# ---------------------- AUTH HELPERS ---------------------- #
def decode_token_payload(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception as e:
        short = (token[:40] + "...") if token else "<no-token>"
        logger.exception("Token verify failed: token_prefix=%s, error=%s", short, e)
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_patient(token: str = Depends(oauth2_scheme_patient), db: Session = Depends(get_db)):
    payload = decode_token_payload(token)
    email: str = payload.get("sub")
    patient = db.query(models.Patient).filter(models.Patient.email == email).first()
    if not patient:
        raise HTTPException(status_code=401, detail="Patient not found")
    return patient

def get_current_doctor(token: str = Depends(oauth2_scheme_doctor), db: Session = Depends(get_db)):
    payload = decode_token_payload(token)
    email: str = payload.get("sub")
    doctor = db.query(models.Doctor).filter(models.Doctor.email == email).first()
    if not doctor:
        raise HTTPException(status_code=401, detail="Doctor not found")
    return doctor

def get_current_hospital(token: str = Depends(oauth2_scheme_hospital), db: Session = Depends(get_db)):
    payload = decode_token_payload(token)
    email: str = payload.get("sub")
    hospital = db.query(models.Hospital).filter(models.Hospital.email == email).first()
    if not hospital:
        raise HTTPException(status_code=401, detail="Hospital not found")
    return hospital

def get_current_admin(token: str = Depends(oauth2_scheme_admin), db: Session = Depends(get_db)):
    payload = decode_token_payload(token)
    email: str = payload.get("sub")
    admin = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin

# Helper: generic token decode for endpoints that accept both hospital & admin tokens
def get_actor_from_token(token: str, db: Session):
    payload = decode_token_payload(token)
    role = payload.get("role")
    sub = payload.get("sub")
    if role == "hospital":
        hosp = db.query(models.Hospital).filter(models.Hospital.email == sub).first()
        if not hosp:
            raise HTTPException(status_code=401, detail="Hospital not found")
        return {"role": "hospital", "id": hosp.id, "email": hosp.email, "model": hosp}
    elif role == "admin":
        admin = db.query(models.AdminUser).filter(models.AdminUser.email == sub).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return {"role": "admin", "id": admin.id, "email": admin.email, "model": admin}
    elif role == "doctor":
        doctor = db.query(models.Doctor).filter(models.Doctor.email == sub).first()
        if not doctor:
            raise HTTPException(status_code=401, detail="Doctor not found")
        return {"role": "doctor", "id": doctor.id, "email": doctor.email, "model": doctor}
    elif role == "patient":
        patient = db.query(models.Patient).filter(models.Patient.email == sub).first()
        if not patient:
            raise HTTPException(status_code=401, detail="Patient not found")
        return {"role": "patient", "id": patient.id, "email": patient.email, "model": patient}
    else:
        raise HTTPException(status_code=401, detail="Unknown role in token")

# ---------------------- NEW: Tickets (single table) ---------------------- #
@router.get("/tickets", response_model=list[TicketOut])
def get_tickets(status: str = None, hospital_id: int = None, token: str = Depends(oauth2_scheme_generic), db: Session = Depends(get_db)):
    """
    - hospital token: returns tickets for that hospital
    - admin token: returns all tickets (optionally filter by hospital_id or status)
    - other roles: forbidden
    """
    actor = get_actor_from_token(token, db)
    q = db.query(models.Ticket)

    if actor["role"] == "hospital":
        # hospital sees only its tickets
        q = q.filter(models.Ticket.hospital_id == actor["id"])
        if status:
            q = q.filter(models.Ticket.status == status)
        return q.order_by(models.Ticket.created_at.desc()).all()

    if actor["role"] == "admin":
        # admin sees all, optional filters
        if hospital_id is not None:
            q = q.filter(models.Ticket.hospital_id == hospital_id)
        if status:
            q = q.filter(models.Ticket.status == status)
        return q.order_by(models.Ticket.created_at.desc()).all()

    raise HTTPException(status_code=403, detail="Not authorized to list tickets")

@router.post("/tickets", response_model=TicketOut, status_code=201)
def create_ticket(ticket_in: TicketCreate, token: str = Depends(oauth2_scheme_generic), db: Session = Depends(get_db)):
    """
    Create a ticket.
    - hospital token: ticket belongs to the calling hospital (hospital_id forced)
    - admin token: may set hospital_id in body (or leave null for system ticket)
    """
    actor = get_actor_from_token(token, db)

    # Build ticket
    if actor["role"] == "hospital":
        hospital_id = actor["id"]
        t = models.Ticket(
            hospital_id=hospital_id,
            type=ticket_in.type,
            details=ticket_in.details,
            payload=ticket_in.payload,
            status="open",
            assigned_admin=ticket_in.assigned_admin,
            last_updated_by_hospital=hospital_id
        )
    elif actor["role"] == "admin":
        t = models.Ticket(
            hospital_id=ticket_in.hospital_id,
            type=ticket_in.type,
            details=ticket_in.details,
            payload=ticket_in.payload,
            status="open",
            assigned_admin=ticket_in.assigned_admin,
            last_updated_by_admin=actor["id"]
        )
    else:
        raise HTTPException(status_code=403, detail="Only hospital or admin can create tickets")

    db.add(t)
    db.commit()
    db.refresh(t)
    return t

@router.put("/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, upd: TicketUpdate, token: str = Depends(oauth2_scheme_generic), db: Session = Depends(get_db)):
    """
    Update or close a ticket.
    - hospital can update tickets belonging to their hospital; hospital's updates set last_updated_by_hospital
      and if hospital sets status to 'closed' then closed_by_hospital and closed_at are set.
    - admin can update any ticket; admin updates set last_updated_by_admin and if admin sets status to 'resolved' or 'closed'
      closed_by_admin and closed_at are set.
    """
    actor = get_actor_from_token(token, db)
    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Authorization
    if actor["role"] == "hospital":
        if t.hospital_id != actor["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to modify this ticket")

    # Apply updates
    changed = False
    if upd.details is not None:
        t.details = upd.details
        changed = True
    if upd.payload is not None:
        # Merge or replace policy: replace payload (simpler). Frontend can send merged object if desired.
        t.payload = upd.payload
        changed = True
    if upd.assigned_admin is not None:
        t.assigned_admin = upd.assigned_admin
        changed = True
    if upd.status is not None:
        # handle status transitions and set closed fields depending on actor
        new_status = upd.status
        t.status = new_status
        changed = True
        if new_status in ("closed", "resolved"):
            t.closed_at = datetime.utcnow()
            if actor["role"] == "admin":
                t.closed_by_admin = actor["id"]
            elif actor["role"] == "hospital":
                t.closed_by_hospital = actor["id"]

    # track last updated by
    if actor["role"] == "admin":
        t.last_updated_by_admin = actor["id"]
    elif actor["role"] == "hospital":
        t.last_updated_by_hospital = actor["id"]

    # if a note is provided, attempt to store it in payload.notes (list)
    if upd.note:
        payload = t.payload or {}
        notes = payload.get("notes") if isinstance(payload, dict) else None
        if not isinstance(notes, list):
            notes = []
        notes.append({"by": actor["role"], "by_id": actor["id"], "note": upd.note, "at": datetime.utcnow().isoformat()})
        payload = dict(payload) if isinstance(payload, dict) else {}
        payload["notes"] = notes
        t.payload = payload
        changed = True

    if changed:
        db.add(t)
        db.commit()
        db.refresh(t)

    return t

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
    if not patient or not verify_password(payload.password, patient.password_hash):
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
    return {"token": token, "doctor_id": doctor.id, "name": doctor.name}

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

# ---------------------- PRESCRIPTIONS ---------------------- #
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

    return db.query(models.Prescription).filter(models.Prescription.patient_id == patient_id).order_by(models.Prescription.created_at.desc()).all()

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

# ---------------------- HOSPITAL AUTH & REQUESTS ---------------------- #

@router.post("/hospital/register", status_code=201)
def register_hospital(payload: HospitalRegisterRequest, db: Session = Depends(get_db), request: Request = None):
    try:
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

        # Create a signup ticket in the central tickets table
        try:
            signup_ticket = models.Ticket(
                hospital_id=hospital.id,
                type="onboard_hospital",
                details=f"Signup request for {payload.name}",
                payload={"name": payload.name, "email": payload.email, "city": payload.city},
                status="open",
                last_updated_by_hospital=hospital.id
            )
            db.add(signup_ticket)
            db.commit()
        except Exception as ticket_err:
            db.rollback()
            print("Warning: signup_ticket creation failed:", file=sys.stdout)
            traceback.print_exc(file=sys.stdout)

        # create token for auto-login
        try:
            token = create_access_token({"sub": hospital.email, "role": "hospital", "hospital_id": hospital.id})
        except Exception:
            token_payload = {
                "sub": str(hospital.email),
                "role": "hospital",
                "hospital_id": str(hospital.id),
                "exp": datetime.utcnow() + timedelta(hours=12)
            }
            token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

        return {
            "token": token,
            "hospital": {
                "id": hospital.id,
                "name": hospital.name,
                "email": hospital.email,
                "city": hospital.city,
                "status": hospital.status
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print("register_hospital: unexpected error", file=sys.stdout)
        traceback.print_exc(file=sys.stdout)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/hospital/login")
def hospital_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    hospital = db.query(models.Hospital).filter(models.Hospital.email == form_data.username).first()
    if not hospital or not verify_password(form_data.password, hospital.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token({"sub": hospital.email, "role": "hospital", "hospital_id": hospital.id})
    return {"token": token, "hospital_id": hospital.id}

# Legacy wrapper endpoints kept for compatibility (they now call the central ticket endpoints)
@router.post("/hospital/requests")
def create_hospital_request(payload: TicketCreate, hospital: models.Hospital = Depends(get_current_hospital), db: Session = Depends(get_db)):
    # alias for POST /tickets by hospital
    token = None
    # we can call create_ticket via internal logic instead of making HTTP call
    t = models.Ticket(
        hospital_id=hospital.id,
        type=payload.type,
        details=payload.details,
        payload=payload.payload,
        status="open",
        last_updated_by_hospital=hospital.id
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"msg": "Request created", "request_id": t.id}

@router.get("/hospital/requests")
def list_hospital_requests(hospital: models.Hospital = Depends(get_current_hospital), db: Session = Depends(get_db)):
    return db.query(models.Ticket).filter(models.Ticket.hospital_id == hospital.id).order_by(models.Ticket.created_at.desc()).all()

@router.get("/hospital/dashboard")
def hospital_dashboard(hospital: models.Hospital = Depends(get_current_hospital), db: Session = Depends(get_db)):
    staff_count = db.query(models.Staff).filter(models.Staff.hospital_id == hospital.id).count() if hasattr(models, "Staff") else 0
    doctor_count = db.query(models.Doctor).filter(models.Doctor.hospital_id == hospital.id).count() if hasattr(models, "Doctor") else 0
    pro_count = db.query(models.Pro).filter(models.Pro.hospital_id == hospital.id).count() if hasattr(models, "Pro") else 0
    ticket_count = db.query(models.Ticket).filter(models.Ticket.hospital_id == hospital.id).count()
    return {"staff_count": staff_count, "doctor_count": doctor_count, "pro_count": pro_count, "ticket_count": ticket_count}

# ---------------------- ADMIN AUTH & REQUESTS ---------------------- #
@router.post("/auth/admin/login")
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(models.AdminUser).filter(models.AdminUser.email == payload.email).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    token = create_access_token({"sub": admin.email, "role": "admin", "id": admin.id})
    return {"token": token, "admin_id": admin.id, "name": admin.name}

@router.get("/admin/requests")
def admin_list_requests(status: str = None, hospital_id: int = None, current_admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    q = db.query(models.Ticket)
    if status:
        q = q.filter(models.Ticket.status == status)
    if hospital_id is not None:
        q = q.filter(models.Ticket.hospital_id == hospital_id)
    return q.order_by(models.Ticket.created_at.desc()).all()

@router.get("/admin/requests/{request_id}")
def admin_get_request(request_id: int, current_admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    r = db.query(models.Ticket).filter(models.Ticket.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    return r

@router.post("/admin/requests/{request_id}/action")
def admin_take_action(request_id: int, action: dict, current_admin: models.AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Keep a simple admin action endpoint for compatibility. `action` should be JSON like:
      { "action": "assign" | "start" | "resolve" | "reject" | "approve_signup", "assign_to": <admin_id> }
    This is a convenience wrapper that maps to ticket updates in the central table.
    """
    r = db.query(models.Ticket).filter(models.Ticket.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Not found")

    act = action.get("action")
    if act == "assign" and action.get("assign_to"):
        r.assigned_admin = action.get("assign_to")
        r.status = "in_progress"
    elif act == "start":
        r.status = "in_progress"
    elif act == "resolve":
        r.status = "resolved"
        r.closed_at = datetime.utcnow()
        r.closed_by_admin = current_admin.id
    elif act == "reject":
        r.status = "rejected"
    elif act == "approve_signup":
        if r.hospital_id:
            hosp = db.query(models.Hospital).filter(models.Hospital.id == r.hospital_id).first()
            if hosp:
                hosp.status = "active"
                r.status = "resolved"
                db.add(hosp)
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    r.last_updated_by_admin = current_admin.id
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
