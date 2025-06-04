import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


@dataclass
class CollectionCaseEntity:
    id:               uuid.UUID
    patient_id:       uuid.UUID
    contract_id:      uuid.UUID
    installment_id:   uuid.UUID
    clinic_id:        uuid.UUID
    opened_at:        datetime
    amount:           Decimal
    deal_id:          int | None              # link p/ Pipedrive
    status:           Literal["open", "closed"]
