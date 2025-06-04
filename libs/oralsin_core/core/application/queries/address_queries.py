from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetAddressQuery:
    id: str

class ListAddressesQuery(PaginatedQueryDTO[dict]):
    """Filtros opcionais em `filtros` (ex: {'city': 'São Paulo'})"""
    pass
