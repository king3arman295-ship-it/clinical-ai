from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class DoctorCreate(BaseModel):
    full_name: str
    specialization: str
    qualification: str | None = None
    phone: str | None = None
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    consultation_fee: int | None = None
    experience_years: int | None = None
    available: bool = True


class DoctorAvailabilityUpdate(BaseModel):
    available: bool


class DoctorUpdate(BaseModel):
    full_name: str | None = None
    specialization: str | None = None
    qualification: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    consultation_fee: int | None = None
    experience_years: int | None = None
    available: bool | None = None


class DoctorResponse(BaseModel):
    id: int
    full_name: str
    specialization: str
    qualification: str | None
    phone: str | None
    email: str | None
    consultation_fee: int | None
    experience_years: int | None
    available: bool

    model_config = ConfigDict(from_attributes=True)

    @field_validator("available", mode="before")
    @classmethod
    def default_available_if_null(cls, v):
        # Older rows may have NULL here (column allows it, but the model's
        # intended default is True) — treat unset as available rather than
        # crashing the whole /doctors/ list.
        return True if v is None else v
