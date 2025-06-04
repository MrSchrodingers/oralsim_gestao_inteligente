from abc import ABC, abstractmethod

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
