from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.user_clinic_entity import UserClinicEntity
from oralsin_core.core.domain.entities.user_entity import UserEntity


class UserClinicRepository(ABC):
    @abstractmethod
    def create_user_with_clinic(*, email: str, password_hash: str,
                            name: str, clinic_id: str, **extra) -> UserEntity:
        ...
    
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

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[UserClinicEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...