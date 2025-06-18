import uuid
from dataclasses import dataclass
from typing import Any

from notification_billing.core.application.cqrs import PaginatedQueryDTO, QueryDTO


@dataclass(frozen=True)
class ListLettersQuery(PaginatedQueryDTO[dict[str, Any]]):
    """Query paginada para listar todas as cartas, enviadas e agendadas."""
    pass

@dataclass(frozen=True)
class GetLetterPreviewQuery(QueryDTO[dict[str, Any]]):
    """Query para obter o preview de uma carta específica."""
    item_id: uuid.UUID
    item_type: str  # 'history' or 'schedule'