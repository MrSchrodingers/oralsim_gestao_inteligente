from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class RegistrationRequestEntity(EntityMixin):
    id: uuid.UUID
    email: str
    password_hash: str
    name: str
    clinic_name: str
    cordial_billing_config: int
    status: Literal['pending', 'approved', 'rejected'] = 'pending'
    created_at: datetime | None = None
    updated_at: datetime | None = None