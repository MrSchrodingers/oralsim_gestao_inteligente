from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListUsersQuery(QueryDTO):
    """
    Query para listar usuários, com filtros embutidos em `params`.
    """
    name: str = "ListUsersQuery"
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True)
class GetUserQuery(QueryDTO):
    """
    Query para recuperar um usuário por ID.
    """
    user_id: str