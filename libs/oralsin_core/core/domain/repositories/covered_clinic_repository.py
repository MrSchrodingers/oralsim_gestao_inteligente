from abc import ABC, abstractmethod

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