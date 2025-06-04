from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class FlowStepConfigEntity(EntityMixin):
    id: uuid.UUID
    step_number: int
    channels: list[str]
    cooldown_days: int = 7
    active: bool = True
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def next_step(self) -> int:
        return self.step_number + 1

    def next_run_date(self, from_date: datetime) -> datetime:
        return from_date + timedelta(days=self.cooldown_days)