from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class PendingSyncEntity(EntityMixin):
    id: uuid.UUID
    object_type: str
    object_api_id: int | None
    action: str
    new_data: dict[str, Any]
    old_data: dict[str, Any] | None = None
    status: Literal['pending','approved','rejected','applied'] = 'pending'
    processed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def approve(self) -> None:
        self.status = 'approved'
        self.updated_at = datetime.utcnow()

    def reject(self) -> None:
        self.status = 'rejected'
        self.updated_at = datetime.utcnow()

    def mark_applied(self) -> None:
        self.status = 'applied'
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def __str__(self) -> str:
        return f"PendingSync({self.id}) [{self.object_type}:{self.action}] - {self.status}"