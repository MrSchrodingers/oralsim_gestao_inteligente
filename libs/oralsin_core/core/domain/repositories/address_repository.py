from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.address_entity import AddressEntity


class AddressRepository(ABC):
    @abstractmethod
    def find_by_id(self, address_id: str) -> AddressEntity | None:
        """Recupera um Address pelo seu ID, ou None se não existir."""
        ...

    @abstractmethod
    def find_all(self) -> list[AddressEntity]:
        """Retorna todos os endereços cadastrados."""
        ...

    @abstractmethod
    def save(self, address: AddressEntity) -> AddressEntity:
        """Cria ou atualiza um Address."""
        ...

    @abstractmethod
    def delete(self, address_id: str) -> None:
        """Remove um Address pelo seu ID."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[AddressEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...