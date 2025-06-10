from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.patient_entity import PatientEntity


class PatientRepository(ABC):
    @abstractmethod
    def find_by_id(self, patient_id: str) -> PatientEntity | None:
        """Retorna um paciente pelo ID interno."""
        ...

    @abstractmethod
    def find_by_clinic(self, clinic_id: str) -> list[PatientEntity]:
        """Lista pacientes de uma clínica."""
        ...

    @abstractmethod
    def save(self, patient: PatientEntity) -> PatientEntity:
        """Cria ou atualiza um Patient."""
        ...

    @abstractmethod
    def delete(self, patient_id: str) -> None:
        """Remove um Patient pelo ID."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[PatientEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...