from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class ClinicPhoneEntity(EntityMixin):
    id: uuid.UUID
    clinic_id: uuid.UUID
    phone_number: str
    contact_phone: str | None = None
    phone_type: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def formatted(self) -> str:
        return f"[{self.phone_type or 'phone'}] {self.phone_number}"