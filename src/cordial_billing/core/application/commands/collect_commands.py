from dataclasses import dataclass

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class SyncOldDebtsCommand(EntityMixin):
    """
    Identifica parcelas vencidas há >= min_days (default 90) e cria CollectionCase.
    """
    clinic_id: str
    min_days: int = 90
