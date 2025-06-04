from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class DebtEscalatedEvent:
    case_id: UUID
    occurred_at: datetime = datetime.utcnow()
