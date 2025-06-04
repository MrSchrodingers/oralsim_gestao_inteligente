from dataclasses import dataclass

from notification_billing.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetContactHistoryQuery:
    id: str

class ListContactHistoryQuery(PaginatedQueryDTO[dict]):
    pass
