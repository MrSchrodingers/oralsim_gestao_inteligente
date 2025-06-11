from abc import ABC, abstractmethod
from datetime import datetime

from notification_billing.core.domain.entities.pending_call_entity import PendingCallEntity


class PendingCallRepository(ABC):
    @abstractmethod
    def create(self, *, patient_id: str, contract_id: str, clinic_id: str,  # noqa: PLR0913
               schedule_id: str | None, current_step: int, scheduled_at: datetime) -> PendingCallEntity: 
      ...
      
    @abstractmethod
    def set_done(self, call_id: str, success: bool, notes: str | None = None) -> None: 
      ...
      
    @abstractmethod
    def list_pending(self, clinic_id: str, before: datetime) -> list[PendingCallEntity]: 
      ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> tuple[list[PendingCallEntity], int]:
        """Retorna PagedResult contendo lista de PendingCallEntity e total,
        aplicando paginação sobre PendingCallModel.

        - filtros: dicionário de filtros
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...