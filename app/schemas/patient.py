from pydantic import BaseModel, ConfigDict, EmailStr


class PatientCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr | None = None


class PatientUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None


class PatientResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None

    model_config = ConfigDict(from_attributes=True)