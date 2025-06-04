from dataclasses import dataclass

from notification_billing.core.application.cqrs import Query


@dataclass(slots=True, frozen=True)
class ListOverdue90PlusQuery(Query):
    clinic_id: str
    page: int
    page_size: int = 500
