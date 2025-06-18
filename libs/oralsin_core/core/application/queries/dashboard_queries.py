from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO
from oralsin_core.core.application.dtos.dashboard_dto import DashboardDTO
from oralsin_core.core.application.services.dashboard_service import DashboardService


@dataclass(frozen=True, slots=True)
class GetDashboardSummaryQuery(QueryDTO):
    user_id: str
    filtros: dict[str, str]

@dataclass(frozen=True, slots=True)
class GetDashboardReportQuery(QueryDTO):
    user_id: str
    filtros: dict[str, str]
        
class GetDashboardSummaryQueryHandler:
    """Handler registrado no QueryBus."""

    def __init__(self, dashboard_service: DashboardService):
        self._svc = dashboard_service

    def __call__(self, q: GetDashboardSummaryQuery) -> DashboardDTO:
        return self._svc.get_summary(
            user_id=q.user_id,
            start_date=q.filtros.get("start_date"),
            end_date=q.filtros.get("end_date"),
        )

    handle = __call__ 