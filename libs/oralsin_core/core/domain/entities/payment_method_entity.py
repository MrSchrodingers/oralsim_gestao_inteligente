from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class PaymentMethodEntity(EntityMixin):
    id: uuid.UUID
    oralsin_payment_method_id: int
    name: str
    created_at: datetime | None = None