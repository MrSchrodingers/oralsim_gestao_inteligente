from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Union

from notification_billing.core.domain.entities.contact_history_entity import ContactHistoryEntity
from notification_billing.core.domain.entities.contact_schedule_entity import (
    ContactScheduleEntity,  # se existir
)
from plugins.django_interface.models import (
    ContactSchedule as ContactScheduleModel,
)

ScheduleLike = Union[ContactScheduleModel, ContactScheduleEntity]  # noqa: UP007

class ContactHistoryRepository(ABC):
    @abstractmethod
    def save(self, history: ContactHistoryEntity) -> ContactHistoryEntity:
        """Persiste um registro de histórico de contato."""
        ...
    
    @abstractmethod
    def save_from_schedule(  # noqa: PLR0913
        self,
        schedule: ScheduleLike,
        sent_at: datetime,
        success: bool,
        channel: str,
        feedback: str | None = None,
        observation: str | None = None,
        message: Any | None = None,
    ) -> ContactHistoryEntity:
        """Cria um histórico de contato a partir de um agendamento ContactScheduleModel,
        registrando os dados relevantes para auditoria.
        """
        ...
        
    @abstractmethod
    def find_by_id(self, history_id: str) -> ContactHistoryEntity | None:
        """Recupera um histórico de contato pelo seu ID."""
        ...
    
    @abstractmethod
    def get_latest_by_clinic(self, clinic_id: str, limit: int = 5) -> list[ContactHistoryEntity]:
        """
        Busca os últimos N registros de histórico de contato para uma clínica,
        ordenados pelo mais recente.
        """
        ...