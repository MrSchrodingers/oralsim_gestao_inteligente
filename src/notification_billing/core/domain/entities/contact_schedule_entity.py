from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class ContactScheduleEntity(EntityMixin):
    id: uuid.UUID
    patient_id: uuid.UUID
    contract_id: uuid.UUID | None
    clinic_id: uuid.UUID
    current_step: int
    scheduled_date: datetime
    notification_trigger: str | None = None
    advance_flow: bool = False
    channel: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_due(self, now: datetime | None = None) -> bool:
        now = now or datetime.utcnow()
        return self.scheduled_date <= now