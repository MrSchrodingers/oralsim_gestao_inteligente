from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContratoDTO, OralsinParcelaAtualDetalheDTO
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
    def existing_oralsin_ids(self, ids: list[int]) -> set[int]:
        ...
        
    @abstractmethod
    def count_overdue_by_contract(self, contract_id: str) -> int:
        """
        Conta de forma eficiente o número total de parcelas vencidas e
        não recebidas para um contrato específico.

        Returns:
            A contagem total de parcelas em atraso.
        """
        ...
        
    @abstractmethod
    def save_many(self, installments: list[InstallmentEntity]) -> None:
        """
        Cria ou atualiza uma lista de parcelas de forma eficiente e em lote.
        """
        ...
        
    @abstractmethod    
    def find_by_contract_ids(self, contract_ids: list[str]) -> list[InstallmentEntity]:
        """
        Busca todas as parcelas associadas a uma lista de IDs de contrato.
        """
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
    def merge_installments(self, parcelas: list, contrato: OralsinContratoDTO | None, parcela_atual: OralsinParcelaAtualDetalheDTO  | None, contract_id: str):
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

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[InstallmentEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...