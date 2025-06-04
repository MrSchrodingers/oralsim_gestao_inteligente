from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class ClinicEntity(EntityMixin):
    id: uuid.UUID
    oralsin_clinic_id: int
    name: str
    cnpj: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def display_name(self) -> str:
        return self.name.upper()
