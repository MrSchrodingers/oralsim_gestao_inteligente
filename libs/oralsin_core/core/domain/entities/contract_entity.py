from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from oralsin_core.core.domain.entities._base import EntityMixin
from oralsin_core.core.domain.entities.payment_method_entity import PaymentMethodEntity


@dataclass(slots=True)
class ContractEntity(EntityMixin):
    id: uuid.UUID
    oralsin_contract_id: int | None
    patient_id: uuid.UUID
    clinic_id: uuid.UUID
    status: Literal['ativo','inativo','cancelado'] = 'ativo'
    contract_version: str | None = None
    remaining_installments: int = 0
    overdue_amount: float = 0.0
    first_billing_date: date | None = None
    negotiation_notes: str | None = None
    payment_method: PaymentMethodEntity | None = None
    final_contract_value: float | None = None
    do_notifications: bool = False
    do_billings: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def days_overdue(self) -> int:
        if self.first_billing_date and date.today() > self.first_billing_date:
            return (date.today() - self.first_billing_date).days
        return 0