from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime


# ───────────────────────────────────────────────
# Event Base e Domain Events
# ───────────────────────────────────────────────
@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

# ╭──────────────────────────────────────────────╮
# │ 1. Clínicas                                 │
# ╰──────────────────────────────────────────────╯
@dataclass(frozen=True)
class ClinicRegisteredEvent(DomainEvent):
    clinic_id: uuid.UUID
    oralsin_clinic_id: int | None
    name: str

# ╭──────────────────────────────────────────────╮
# │ 2. Pacientes                                │
# ╰──────────────────────────────────────────────╯
@dataclass(frozen=True)
class PatientRegisteredEvent(DomainEvent):
    patient_id: uuid.UUID
    oralsin_patient_id: int | None
    name: str
    clinic_id: uuid.UUID

# ╭──────────────────────────────────────────────╮
# │ 3. Contratos                                │
# ╰──────────────────────────────────────────────╯
@dataclass(frozen=True)
class ContractCreatedEvent(DomainEvent):
    contract_id: uuid.UUID
    oralsin_contract_id: int | None
    patient_id: uuid.UUID
    clinic_id: uuid.UUID
    status: str
    first_billing_date: date | None

# ╭──────────────────────────────────────────────╮
# │ 4. Parcelas                                 │
# ╰──────────────────────────────────────────────╯
@dataclass(frozen=True)
class InstallmentScheduledEvent(DomainEvent):
    installment_id: uuid.UUID
    contract_id: uuid.UUID
    due_date: date
    amount: float

@dataclass(frozen=True)
class PaymentReceivedEvent(DomainEvent):
    installment_id: uuid.UUID
    amount: float
    received_at: datetime

# ╭──────────────────────────────────────────────╮
# │ 7. Pending Sync                             │
# ╰──────────────────────────────────────────────╯
@dataclass(frozen=True)
class PendingSyncRequestedEvent(DomainEvent):
    sync_id: uuid.UUID
    object_type: str
    object_api_id: int | None
    action: str

# ╭──────────────────────────────────────────────╮
# │ 8. Usuários                                 │
# ╰──────────────────────────────────────────────╯

@dataclass(frozen=True)
class CoveredClinicRegisteredEvent(DomainEvent):
    clinic_id: uuid.UUID
    oralsin_clinic_id: int
    name: str

@dataclass(frozen=True)
class UserClinicLinkedEvent(DomainEvent):
    user_id: str
    clinic_id: str
