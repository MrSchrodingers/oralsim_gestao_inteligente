from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class MessageEntity(EntityMixin):
    id: uuid.UUID
    type: str
    content: str
    step: int
    clinic_id: uuid.UUID | None = None
    is_default: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def preview(self, length: int = 50) -> str:
        return (self.content[:length] + '...') if len(self.content) > length else self.content