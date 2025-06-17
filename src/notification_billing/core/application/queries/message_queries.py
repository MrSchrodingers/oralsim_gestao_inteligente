from dataclasses import dataclass
from typing import Any

from oralsin_core.core.application.cqrs import PaginatedQueryDTO, QueryDTO


@dataclass(frozen=True)
class GetMessageQuery(QueryDTO):
    message_id: str
    filtros: dict[str, Any]

class ListMessagesQuery(PaginatedQueryDTO):
    filtros: dict[str, Any]