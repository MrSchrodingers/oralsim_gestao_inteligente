from datetime import datetime

from pydantic import BaseModel


class ContactScheduleDTO(BaseModel):
    """
    Projeção de um agendamento de contato para API externa ou UI.
    """
    id: str
    patient_id: str
    contract_id: str | None
    clinic_id: str
    installment_id: str
    current_step: int
    channel: str
    scheduled_date: datetime
    status: str | None = None
    installment_id: str | None = None
