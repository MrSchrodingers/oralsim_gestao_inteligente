from datetime import date

from pydantic import BaseModel


class ContractQueryDTO(BaseModel):
    """
    DTO para filtros de listagem de contratos.
    """
    clinic_id: str | None = None
    patient_id: str | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
