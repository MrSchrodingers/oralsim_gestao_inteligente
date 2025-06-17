from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from notification_billing.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListDueContactsQuery(QueryDTO):
    filtros: dict[str, Any]
    page: int = 1
    page_size: int = 50