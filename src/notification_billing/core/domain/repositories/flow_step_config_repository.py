from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from oralsin_core.core.application.cqrs import PagedResult

from notification_billing.core.domain.entities.flow_step_config_entity import FlowStepConfigEntity


class FlowStepConfigRepository(ABC):
    @abstractmethod
    def list_active_steps(self) -> Sequence[FlowStepConfigEntity]:
        """Retorna todos os FlowStepConfig ativos ordenados."""
        ...
        
    @abstractmethod
    def all(self) -> list[FlowStepConfigEntity]:  
        """Retorna todos os FlowStepConfig."""
        ...
          
    @abstractmethod
    def find_by_step(self, step_number: int) -> FlowStepConfigEntity | None:
        """Retorna o FlowStepConfigEntity por step_number."""
        ...    
        
    @abstractmethod
    def find_by_id(self, payment_method_id: str) -> FlowStepConfigEntity | None:
        """Retorna o FlowStepConfigEntity por payment_method_id."""
        ...      
        
    @abstractmethod
    def get_active(self, step_number: int) -> FlowStepConfigEntity | None:
        """Retorna o FlowStepConfigEntity ativo por step_number."""
        ...
        
    @abstractmethod
    def max_active_step(self) -> int:
        """Retorna o maior step_number ativo."""
        ...
    
    @abstractmethod
    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[FlowStepConfigEntity]:
        ...