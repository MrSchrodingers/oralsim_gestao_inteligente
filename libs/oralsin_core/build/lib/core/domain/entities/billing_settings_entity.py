from dataclasses import dataclass
from uuid import UUID

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(frozen=True, slots=True)
class BillingSettingsEntity(EntityMixin):
    clinic_id: UUID
    min_days_overdue: int
