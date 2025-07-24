# entities/collection_case.py

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(frozen=True, slots=True)
class CollectionCaseEntity(EntityMixin):
    id:               uuid.UUID
    patient_id:       uuid.UUID
    contract_id:      uuid.UUID
    installment_id:   uuid.UUID
    clinic_id:        uuid.UUID
    opened_at:        datetime
    amount:           Decimal
    deal_id:          int | None   
    stage_id:         int | None 
    last_stage_id:    int | None  
    deal_sync_status: Literal["pending", "created", "updated", "error"]
    status:           Literal["open", "closed"]
