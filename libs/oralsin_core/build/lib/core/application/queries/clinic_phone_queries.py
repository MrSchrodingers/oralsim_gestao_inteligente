from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetClinicPhoneQuery:
    id: str

class ListClinicPhonesQuery(PaginatedQueryDTO[dict]):
    pass
