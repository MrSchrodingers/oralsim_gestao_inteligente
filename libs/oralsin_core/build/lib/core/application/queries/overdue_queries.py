from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class ListPatientsInDebtQuery(PaginatedQueryDTO[dict]):
    filtros: dict  # ex: {"clinic_id": uuid, "min_overdue_days": 7}
    page: int = 1
    page_size: int = 50
