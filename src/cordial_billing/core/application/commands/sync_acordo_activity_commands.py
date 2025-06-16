from dataclasses import dataclass

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class SyncAcordoActivitiesCommand(EntityMixin):
    """Sincroniza atividades 'call' (acordo fechado)."""
    clinic_id: str 
    after_id: int = 0
    batch_size: int = 500
