from fastapi import APIRouter
from app import models

router = APIRouter()

@router.get("/patients")
def get_patients():
    return [{"id": 1, "name": "John Doe"}, {"id": 2, "name": "Jane Smith"}]

@router.post("/patients")
def create_patient(patient: models.Patient):
    return {"message": "Patient created", "data": patient}
