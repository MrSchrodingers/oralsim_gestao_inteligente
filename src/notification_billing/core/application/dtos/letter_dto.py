import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LetterListItemDTO:
    """DTO para um item na lista de cartas enviadas ou agendadas."""
    id: uuid.UUID
    patient_name: str
    contract_id: str
    status: str  # "Enviada" ou "Agendada"
    relevant_date: datetime
    item_type: str # 'history' ou 'schedule'