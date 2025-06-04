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
        
    @abstractmethod
    def get_active(self, step_number: int) -> FlowStepConfigEntity | None:
        """Retorna o FlowStepConfigEntity ativo por step_number."""
        ...
        
    @abstractmethod
    def max_active_step(self) -> int:
        """Retorna o maior step_number ativo."""
        ...