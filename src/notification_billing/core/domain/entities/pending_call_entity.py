import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from oralsin_core.core.domain.entities.contract_entity import ContractEntity
from oralsin_core.core.domain.entities.patient_entity import PatientEntity

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class PendingCallEntity(EntityMixin):
    id: uuid.UUID
    clinic_id: uuid.UUID

    # --- relacionamento --- #
    patient: PatientEntity | None = None
    contract: ContractEntity | None = None   # ou Dict se não tiver entidade específica

    # --- campos de fluxo --- #
    current_step: int = 0
    schedule_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None
    attempts: int = 0
    status: str = "pending"
    last_attempt_at: datetime | None = None
    result_notes: str | None = None

    # ids ainda acessíveis para busca rápida --------------------------------
    @property
    def patient_id(self) -> uuid.UUID | None:
        return self.patient.id if self.patient else None

    @property
    def contract_id(self) -> uuid.UUID | None:
        return self.contract.id if self.contract else None

    # serialização ----------------------------------------------------------
    def to_dict(self) -> dict[str, any]:
        data = {
            "id": str(self.id),
            "clinic_id": str(self.clinic_id),
            "current_step": self.current_step,
            "schedule_id": str(self.schedule_id) if self.schedule_id else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "attempts": self.attempts,
            "status": self.status,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "result_notes": self.result_notes,
        }
        if self.patient:
            data["patient"] = self.patient.to_dict()
        if self.contract:
            data["contract"] = {
                "id": str(self.contract.id),
                "overdue_amount": str(
                    getattr(self.contract, "overdue_amount", Decimal("0.00"))
                ),
                "due_date": getattr(self.contract, "due_date", None),
            }
        return data
