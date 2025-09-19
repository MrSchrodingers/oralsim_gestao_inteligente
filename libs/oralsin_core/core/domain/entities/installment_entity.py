from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from oralsin_core.core.domain.entities._base import EntityMixin
from oralsin_core.core.domain.entities.payer_entity import PayerEntity
from oralsin_core.core.domain.entities.payment_method_entity import PaymentMethodEntity


@dataclass(slots=True)
class InstallmentEntity(EntityMixin):
    id: uuid.UUID
    contract_id: uuid.UUID
    installment_number: int
    contract_version: int 
    due_date: date
    installment_amount: float
    received: bool
    schedule: bool | None 
    oralsin_installment_id: int | None 
    payer: PayerEntity | None = None 
    installment_status: str | None = None
    payment_method: PaymentMethodEntity | None = None
    is_current: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_overdue(self) -> bool:
        return not self.received and self.due_date < date.today()