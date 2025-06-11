from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(frozen=True)
class PendingCallEntity(EntityMixin):
    id: uuid.UUID
    patient_id: uuid.UUID
    contract_id: uuid.UUID
    clinic_id: uuid.UUID
    schedule_id: uuid.UUID | None
    current_step: int
    scheduled_at: datetime
    attempts: int
    status: str
    last_attempt_at: datetime | None
    result_notes: str | None
