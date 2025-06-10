from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.clinic_data_entity import ClinicDataEntity


class ClinicDataRepository(ABC):
    @abstractmethod
    def find_by_id(self, data_id: str) -> ClinicDataEntity | None:
        """Retorna um dado de clínica pelo ID."""
        ...

    @abstractmethod
    def list_by_clinic(self, clinic_id: str) -> list[ClinicDataEntity]:
        """Lista todos os dados associados a uma clínica."""
        ...

    @abstractmethod
    def save(self, data: ClinicDataEntity) -> ClinicDataEntity:
        """Cria ou atualiza um ClinicData."""
        ...

    @abstractmethod
    def delete(self, data_id: str) -> None:
        """Remove um ClinicData pelo ID."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[ClinicDataEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...