from abc import ABC, abstractmethod
from typing import Any

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity


class InstallmentRepository(ABC):
    @abstractmethod
    def list_overdue(
        self,
        contract_id: str,
        min_days_overdue: int,
        offset: int,
        limit: int
    ) -> PagedResult[InstallmentEntity]:
        """Lista parcelas vencidas paginadas."""
        ...
        
    @abstractmethod
    def list_current_overdue(
        self,
        contract_id: str,
        min_days_overdue: int,
        offset: int,
        limit: int,
        *,
        contract_version: int | None = None,
    ) -> PagedResult[InstallmentEntity]:
        """Lista parcelas vencidas paginadas."""
        ...
        
    @abstractmethod
    def merge_installments(parcelas: list, parcela_atual: Any | None, contract_id):
        """Retorna uma lista de InstallmentEntity única, priorizando parcelaAtualDetalhe."""
        ...
        
    @abstractmethod
    def get_trigger_installment(self, contract_id: str) -> InstallmentEntity | None:
        """Recupera a primeira parcela vencida."""
        ...
        
    @abstractmethod
    def has_overdue(self, contract_id: str, min_days_overdue: int) -> bool:
        """Verifica se existem parcelas vencidas."""
        ...
    
    @abstractmethod
    def get_current_installment(self, contract_id: str) -> InstallmentEntity | None:
        """Recupera a parcela atual."""
        ...
             
    @abstractmethod
    def find_by_id(self, installment_id: str) -> InstallmentEntity | None:
        """Recupera parcela por ID."""
        ...

    @abstractmethod
    def save(self, installment: InstallmentEntity) -> InstallmentEntity:
        """Cria ou atualiza uma parcela."""
        ...

    @abstractmethod
    def delete(self, installment_id: str) -> None:
        """Remove uma parcela."""
        ...
