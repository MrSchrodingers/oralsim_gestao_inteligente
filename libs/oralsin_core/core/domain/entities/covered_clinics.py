from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class CoveredClinicEntity(EntityMixin):
    id: uuid.UUID
    oralsin_clinic_id: int
    name: str
    cnpj: str | None = None
    corporate_name: str | None = None
    acronym: str | None = None
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_active_str(self) -> str:
        return "Ativa" if self.active else "Inativa"