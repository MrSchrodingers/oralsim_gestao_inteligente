from dataclasses import dataclass

from notification_billing.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetMessageQuery:
    id: str

class ListMessagesQuery(PaginatedQueryDTO[dict]):
    pass
