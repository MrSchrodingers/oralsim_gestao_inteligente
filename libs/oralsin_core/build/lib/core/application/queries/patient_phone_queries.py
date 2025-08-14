from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetPatientPhoneQuery:
    id: str

class ListPatientPhonesQuery(PaginatedQueryDTO[dict]):
    pass
