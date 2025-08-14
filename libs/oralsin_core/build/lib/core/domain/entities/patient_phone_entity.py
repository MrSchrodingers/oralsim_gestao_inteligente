from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class PatientPhoneEntity(EntityMixin):
    id: uuid.UUID
    patient_id: uuid.UUID
    phone_number: str
    phone_type: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None