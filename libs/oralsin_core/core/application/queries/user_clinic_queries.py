from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetUserClinicQuery:
    id: str

class ListUserClinicsQuery(PaginatedQueryDTO[dict]):
    pass
