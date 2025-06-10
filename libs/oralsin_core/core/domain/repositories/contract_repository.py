from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.contract_entity import ContractEntity


class ContractRepository(ABC):
    @abstractmethod
    def find_by_id(self, contract_id: str) -> ContractEntity | None:
        """Recupera um contrato por ID."""
        ...

    @abstractmethod
    def list_by_clinic(self, clinic_id: str) -> list[ContractEntity]:
        """Lista contratos de uma clínica."""
        ...

    @abstractmethod
    def save(self, contract: ContractEntity) -> ContractEntity:
        """Cria ou atualiza um contrato."""
        ...

    @abstractmethod
    def delete(self, contract_id: str) -> None:
        """Remove um contrato."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[ContractEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...