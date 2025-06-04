from __future__ import annotations

from dataclasses import dataclass

from notification_billing.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListDueContactsQuery(QueryDTO[dict]):
    filtros: dict  # {'clinic_id': uuid.UUID}