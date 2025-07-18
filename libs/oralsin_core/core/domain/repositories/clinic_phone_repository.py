from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.clinic_phone_entity import ClinicPhoneEntity


class ClinicPhoneRepository(ABC):
    @abstractmethod
    def find_by_id(self, phone_id: str) -> ClinicPhoneEntity | None:
        """Recupera um telefone de clínica pelo ID."""
        ...

    @abstractmethod
    def list_by_clinic(self, clinic_id: str) -> list[ClinicPhoneEntity]:
        """Lista os telefones de uma clínica."""
        ...

    @abstractmethod
    def save(self, phone: ClinicPhoneEntity) -> ClinicPhoneEntity:
        """Cria ou atualiza um ClinicPhone."""
        ...

    @abstractmethod
    def delete(self, phone_id: str) -> None:
        """Remove um ClinicPhone pelo ID."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[ClinicPhoneEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...
        