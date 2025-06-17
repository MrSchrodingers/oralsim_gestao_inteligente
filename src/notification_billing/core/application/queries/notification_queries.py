from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListPendingSchedulesQuery(QueryDTO):
    filtros: dict[str, Any]
    page: int = 1
    page_size: int = 50