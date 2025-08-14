from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class UserEntity(EntityMixin):
    id: uuid.UUID
    email: str
    name: str
    clinic_name: str | None = None
    password_hash: str | None = None
    is_active: bool = True
    role: Literal['admin','clinic'] = 'clinic'
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        if self.role not in ('admin','clinic'):
            raise ValueError(f"Role inválida: {self.role}")

    @property
    def is_authenticated(self) -> bool:
        return self.is_active