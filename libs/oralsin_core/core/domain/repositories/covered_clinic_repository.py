from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.covered_clinics import CoveredClinicEntity


class CoveredClinicRepository(ABC):
    @abstractmethod
    def find_by_id(self, covered_id: str) -> CoveredClinicEntity | None:
        """Retorna uma CoveredClinic pelo ID interno."""
        ...

    @abstractmethod
    def find_by_api_id(self, oralsin_id: int) -> CoveredClinicEntity | None:
        """Retorna uma CoveredClinic pelo ID na Oralsin."""
        ...

    @abstractmethod
    def list_all(self) -> list[CoveredClinicEntity]:
        """Retorna todas as clínicas cobertas."""
        ...

    @abstractmethod
    def save(self, clinic: CoveredClinicEntity) -> CoveredClinicEntity:
        """Cria ou atualiza uma CoveredClinic."""
        ...

    @abstractmethod
    def delete(self, clinic_id: str) -> None:
        """Remove uma CoveredClinic pelo ID."""
        ...
        
    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[CoveredClinicEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...