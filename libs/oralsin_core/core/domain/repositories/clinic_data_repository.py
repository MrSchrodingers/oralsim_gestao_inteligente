from abc import ABC, abstractmethod

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
