from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class ContactHistoryEntity(EntityMixin):
    id: uuid.UUID
    patient_id: uuid.UUID
    contract_id: uuid.UUID | None
    clinic_id: uuid.UUID
    contact_type: str
    sent_at: datetime | None
    notification_trigger: str
    advance_flow: bool = False
    feedback_status: str | None = None
    observation: str | None = None
    message_id: uuid.UUID | None = None
    schedule_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def summary(self) -> str:
        ts = self.sent_at.isoformat() if self.sent_at else 'N/A'
        return f"{ts} - {self.contact_type} - {self.feedback_status or 'sem feedback'}"