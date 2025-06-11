from dataclasses import dataclass
from typing import Any

from notification_billing.core.application.cqrs import QueryDTO


@dataclass(frozen=True, slots=True)
class ListPendingCallsQuery(QueryDTO):
    """Lista pendências de ligação com paginação."""
    filtros: dict[str, Any]
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True, slots=True)
class GetPendingCallQuery(QueryDTO):
    """Recupera uma pendência de ligação pelo ID."""
    id: str
    filtros: dict[str, Any]  # para forçar clinic_id, status etc.
