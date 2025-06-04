from dataclasses import dataclass

from notification_billing.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetContactScheduleQuery:
    id: str

class ListContactSchedulesQuery(PaginatedQueryDTO[dict]):
    pass

class ListDueContactsQuery(PaginatedQueryDTO[dict]):
    """Lista agendamentos com scheduled_date <= now e status pendente."""
    pass
