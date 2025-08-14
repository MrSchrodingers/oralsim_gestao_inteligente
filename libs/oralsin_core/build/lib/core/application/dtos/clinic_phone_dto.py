from pydantic import BaseModel


class ClinicPhoneDTO(BaseModel):
    clinic_id: str
    phone_number: str
    phone_type: str | None = None
