import uuid
from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO, QueryDTO


@dataclass(frozen=True)
class GetRegistrationRequestQuery(QueryDTO):
    request_id: uuid.UUID

class ListRegistrationRequestsQuery(PaginatedQueryDTO[dict]):
    pass