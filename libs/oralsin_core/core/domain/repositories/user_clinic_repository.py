from abc import ABC, abstractmethod

from oralsin_core.core.domain.entities.user_clinic_entity import UserClinicEntity


class UserClinicRepository(ABC):
    @abstractmethod
    def find_by_user(self, user_id: str) -> list[UserClinicEntity]:
        """Lista clínicas vinculadas a um usuário."""
        ...

    @abstractmethod
    def find_by_clinic(self, clinic_id: str) -> list[UserClinicEntity]:
        """Lista usuários vinculados a uma clínica."""
        ...

    @abstractmethod
    def save(self, link: UserClinicEntity) -> UserClinicEntity:
        """Cria ou atualiza um vínculo usuário↔clínica."""
        ...

    @abstractmethod
    def delete(self, user_id: str, clinic_id: str) -> None:
        """Remove um vínculo."""
        ...
