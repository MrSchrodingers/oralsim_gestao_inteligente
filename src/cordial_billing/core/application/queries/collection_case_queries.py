from dataclasses import dataclass
from typing import Any

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True, slots=True)
class GetCollectionCaseQuery(QueryDTO):
    collection_case_id: str
    filtros: dict[str, Any]
    

@dataclass(frozen=True, slots=True)
class ListCollectionCasesQuery(QueryDTO):
    """
    Lista com paginação.
    - filtros: ex.: {'clinic_id': '<uuid>'}
    - page: página (1-based)
    - page_size: itens por página
    """
    filtros: dict[str, Any]
    page: int = 1
    page_size: int = 50