from pydantic import BaseModel

class Patient(BaseModel):
    id: int | None = None
    name: str
    age: int | None = None
