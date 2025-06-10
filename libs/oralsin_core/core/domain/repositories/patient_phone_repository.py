from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.patient_phone_entity import PatientPhoneEntity


class PatientPhoneRepository(ABC):
    @abstractmethod
    def save(self, entity: PatientPhoneEntity) -> PatientPhoneEntity:
        ...
    @abstractmethod
    def update(self, entity: PatientPhoneEntity) -> PatientPhoneEntity:
        ...
    @abstractmethod
    def delete(self, phone_id: str) -> None:
        ...
    @abstractmethod
    def find_by_id(self, phone_id: str) -> PatientPhoneEntity | None:
        ...
    @abstractmethod
    def find_all(self) -> list[PatientPhoneEntity]:
        ...
    @abstractmethod
    def find_by_patient(self, patient_id: str) -> list[PatientPhoneEntity]:
        """Retorna todos os telefones cadastrados para um paciente."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[PatientPhoneEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...