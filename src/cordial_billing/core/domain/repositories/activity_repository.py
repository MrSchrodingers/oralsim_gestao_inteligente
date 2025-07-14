from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from cordial_billing.core.domain.entities.pipedrive_activity_entity import PipedriveActivityEntity


class ActivityRepository(ABC):
    @abstractmethod
    async def list_acordo_fechado(self, after_id: int, limit: int = 100) -> Sequence[PipedriveActivityEntity]:
        """Lista atividades do Pipeboard com type='acordo_fechado' maiores que after_id."""
        ...
        
    @abstractmethod    
    async def save_from_pipedrive_json(self, data: dict[str, Any]) -> None:
        """
        Upsert direto na tabela *atividades* a partir do JSON devolvido
        pelo endpoint `/activities` do Pipedrive.
        """
        ...