from typing import Any

from django.utils import timezone
from oralsin_core.adapters.context.request_context import get_current_request

from notification_billing.core.application.cqrs import PagedResult, QueryHandler
from notification_billing.core.application.queries.notification_queries import ListPendingSchedulesQuery


class ListPendingSchedulesHandler(QueryHandler[ListPendingSchedulesQuery, PagedResult[Any]]):
    """
    Handler para listar agendamentos pendentes (vencidos), agora de forma eficiente
    e aplicando todos os filtros recebidos.
    """
    def __init__(self, schedule_repo):
        self.schedule_repo = schedule_repo

    def handle(self, query: ListPendingSchedulesQuery) -> PagedResult[Any]:
        filtros = query.filtros or {}

        req = get_current_request()
        if "clinic_id" not in filtros and req and getattr(req.user, "role", None) == "clinic":
            filtros["clinic_id"] = getattr(req.user, "clinic_id", None)

        filtros["status"] = "pending"
        filtros["scheduled_date__lte"] = timezone.now()

        return self.schedule_repo.list(
            filtros=filtros,
            page=query.page,
            page_size=query.page_size
        )