from pydantic import BaseModel, EmailStr


class CreateRegistrationRequestDTO(BaseModel):
    email: EmailStr
    password: str
    name: str
    clinic_name: str
    cordial_billing_config: int = 90