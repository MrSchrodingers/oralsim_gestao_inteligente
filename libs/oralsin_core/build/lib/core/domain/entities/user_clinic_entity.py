from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class UserClinicEntity(EntityMixin):
    id: uuid.UUID
    user_id: uuid.UUID
    clinic_id: uuid.UUID
    linked_at: datetime | None = None