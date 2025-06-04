from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetClinicDataQuery:
    id: str

class ListClinicDataQuery(PaginatedQueryDTO[dict]):
    pass
