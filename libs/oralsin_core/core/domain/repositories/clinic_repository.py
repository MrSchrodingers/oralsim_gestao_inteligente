from abc import ABC, abstractmethod

from oralsin_core.core.domain.entities.clinic_entity import ClinicEntity


class ClinicRepository(ABC):
    @abstractmethod
    def find_by_id(self, clinic_id: str) -> ClinicEntity | None:
        """Retorna uma clínica pelo seu ID interno."""
        ...

    @abstractmethod
    def find_by_oralsin_id(self, oralsin_id: int) -> ClinicEntity | None:
        """Retorna uma clínica pelo seu ID na Oralsin."""
        ...

    @abstractmethod
    def find_by_name(self, name: str) -> list[ClinicEntity]:
        """Busca clínicas cujo nome contenha o termo informado."""
        ...

    @abstractmethod
    def save(self, clinic: ClinicEntity) -> ClinicEntity:
        """Cria ou atualiza uma Clínica."""
        ...

    @abstractmethod
    def delete(self, clinic_id: str) -> None:
        """Remove uma Clínica pelo ID."""
        ...
        
    @abstractmethod
    def get_or_create_by_oralsin_id(
            self, oralsin_clinic_id: int, *, name: str | None = None, cnpj: str | None = None
        ) -> ClinicEntity:
        ...
