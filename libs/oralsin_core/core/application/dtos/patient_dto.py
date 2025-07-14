from datetime import date

from pydantic import BaseModel, EmailStr


class RegisterPatientsDTO(BaseModel):
    """
    Usado pelo fluxo de sincronização para importar pacientes de uma clínica.
    """
    user_id: str
    initial_due_date: date
    final_due_date: date


class UpdatePatientDTO(BaseModel):
    """
    Atualização pontual de dados do paciente.
    """
    patient_id: str
    name: str | None = None
    cpf: str | None = None
    email: EmailStr | None = None

class PatientDTO(BaseModel):
    clinic_id: str
    oralsin_patient_id: int | None = None
    name: str
    cpf: str | None = None
    address_id: str | None = None
    contact_name: str | None = None
    email: str | None = None
