from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True, slots=True)
class GetDashboardSummaryQuery(QueryDTO):
    user_id: str
