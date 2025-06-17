from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO
from oralsin_core.core.application.dtos.dashboard_dto import DashboardDTO
from oralsin_core.core.application.services.dashboard_service import DashboardService


@dataclass(frozen=True, slots=True)
class GetDashboardSummaryQuery(QueryDTO):
    user_id: str
    
class GetDashboardSummaryQueryHandler:
    """Handler registrado no QueryBus."""

    def __init__(self, dashboard_service: DashboardService):
        self._svc = dashboard_service

    def __call__(self, query: GetDashboardSummaryQuery) -> DashboardDTO:
        return self._svc.get_summary_sync(query.user_id)

    handle = __call__ 