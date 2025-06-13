from dataclasses import dataclass
from typing import Any

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True, slots=True)
class GetFlowStepConfigQuery(QueryDTO):
    payment_method_id: str
    filtros: dict[str, Any]
    

@dataclass(frozen=True, slots=True)
class ListFlowStepConfigsQuery(QueryDTO):
    """
    Lista com paginação.
    - filtros: ex.: {'clinic_id': '<uuid>'}
    - page: página (1-based)
    - page_size: itens por página
    """
    filtros: dict[str, Any]
    page: int = 1
    page_size: int = 50