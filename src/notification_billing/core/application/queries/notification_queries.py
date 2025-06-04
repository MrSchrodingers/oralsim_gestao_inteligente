from __future__ import annotations

from dataclasses import dataclass

from notification_billing.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class ListPendingSchedulesQuery(PaginatedQueryDTO[dict]):
    filtros: dict  # {'clinic_id': str}