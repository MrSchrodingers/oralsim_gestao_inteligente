from abc import ABC, abstractmethod

from oralsin_core.core.domain.entities.user_entity import UserEntity


class UserRepository(ABC):
    @abstractmethod
    def find_by_id(self, user_id: str) -> UserEntity | None:
        """Retorna o usuário por ID."""
        ...

    @abstractmethod
    def find_by_email(self, email: str) -> UserEntity | None:
        """Retorna o usuário com o e-mail informado, ou None."""
        ...

    @abstractmethod
    def find_by_role(self, role: str) -> list[UserEntity]:
        """Lista todos os usuários de um determinado papel."""
        ...

    @abstractmethod
    def find_all(self) -> list[UserEntity]:
        """Retorna todos os usuários."""
        ...

    @abstractmethod
    def save(self, entity: UserEntity) -> UserEntity:
        """Cria ou atualiza um usuário."""
        ...

    @abstractmethod
    def update(self, entity: UserEntity) -> UserEntity:
        """Atualiza um usuário existente."""
        ...

    @abstractmethod
    def delete(self, user_id: str) -> None:
        """Remove um usuário."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> tuple[list[UserEntity], int]:
        """Retorna PagedResult contendo lista de UserEntity e total,
        aplicando paginação sobre UserModel.

        - filtros: dicionário de filtros (ex.: {'role': 'admin', 'email__icontains': 'foo'})
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...