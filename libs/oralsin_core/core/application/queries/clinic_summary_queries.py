from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO
from oralsin_core.core.application.dtos.clinic_summary_dto import ClinicSummaryDTO
from oralsin_core.core.application.services.dashboard_service import DashboardService


@dataclass(frozen=True, slots=True)
class GetClinicSummaryQuery(QueryDTO):
    clinic_id: str
    start_date: str | None = None
    end_date: str | None = None


class GetClinicSummaryQueryHandler:
    def __init__(self, dashboard_service: DashboardService):
        self._svc = dashboard_service

    def __call__(self, q: GetClinicSummaryQuery) -> ClinicSummaryDTO:
        return self._svc.get_clinic_summary(
            clinic_id=q.clinic_id,
            start_date=q.start_date,
            end_date=q.end_date,
        )

    handle = __call__