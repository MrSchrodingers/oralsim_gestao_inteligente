from abc import ABC, abstractmethod
from collections.abc import Sequence

from notification_billing.core.domain.entities.flow_step_config_entity import FlowStepConfigEntity


class FlowStepConfigRepository(ABC):
    @abstractmethod
    def list_active_steps(self) -> Sequence[FlowStepConfigEntity]:
        """Retorna todos os FlowStepConfig ativos ordenados."""
        ...
        
    @abstractmethod
    def find_by_step(self, step_number: int) -> FlowStepConfigEntity | None:
        """Retorna o FlowStepConfigEntity por step_number."""
        ... 