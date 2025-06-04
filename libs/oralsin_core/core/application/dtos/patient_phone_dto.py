from pydantic import BaseModel


class PatientPhoneDTO(BaseModel):
    patient_id: str
    phone_number: str
    phone_type: str | None = None
