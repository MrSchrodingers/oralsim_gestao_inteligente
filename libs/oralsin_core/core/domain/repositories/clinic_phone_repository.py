from abc import ABC, abstractmethod

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
