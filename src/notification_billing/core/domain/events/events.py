from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


# ───────────────────────────────────────────────
# Event Base e Domain Events
# ───────────────────────────────────────────────
@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

# ╭──────────────────────────────────────────────╮
# │ 5. Notificações / Agendamentos               │
# ╰──────────────────────────────────────────────╯
@dataclass(frozen=True)
class NotificationScheduledEvent(DomainEvent):
    schedule_id: uuid.UUID
    patient_id: uuid.UUID
    contract_id: uuid.UUID | None
    step: int
    channel: str
    scheduled_date: datetime

@dataclass(frozen=True)
class NotificationSentEvent(DomainEvent):
    schedule_id: uuid.UUID
    message_id: uuid.UUID
    sent_at: datetime
    channel: str

# ╭──────────────────────────────────────────────╮
# │ 6. Resultado de Contato                    │
# ╰──────────────────────────────────────────────╯
@dataclass(frozen=True)
class ContactHistoryRecordedEvent(DomainEvent):
    history_id: uuid.UUID
    patient_id: uuid.UUID
    contract_id: uuid.UUID | None
    clinic_id: uuid.UUID
    contact_type: str
    sent_at: datetime | None
    feedback_status: str | None

# ╭──────────────────────────────────────────────╮
# │ 9. Histórico de Contato                     │
# ╰──────────────────────────────────────────────╯

@dataclass(frozen=True)
class ContactOutcomeRecordedEvent:
    """
    Evento disparado após registrar o resultado de um contato.
    """
    history_id: str
    feedback_status: str
    observation: str
    recorded_at: datetime = field(default_factory=datetime.utcnow)