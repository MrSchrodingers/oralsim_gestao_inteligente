from typing import Any

from django.utils import timezone

from notification_billing.core.application.cqrs import PagedResult, QueryHandler
from notification_billing.core.application.queries.notification_queries import ListPendingSchedulesQuery
from plugins.django_interface.models import ContactSchedule


class ListPendingSchedulesHandler(
    QueryHandler[ListPendingSchedulesQuery, PagedResult[Any]]
):
    def __init__(self, schedule_repo):
        self.schedule_repo = schedule_repo

    def handle(self, query: ListPendingSchedulesQuery) -> PagedResult[Any]:
        data = [
            s for s in self.schedule_repo.filter(
                clinic_id=query.filtros["clinic_id"],
                status=ContactSchedule.Status.PENDING,
            )
            if s.scheduled_date <= timezone.now()
        ]
        data.sort(key=lambda s: s.scheduled_date)
        total   = len(data)
        offset  = (query.page - 1) * query.page_size
        items   = data[offset : offset + query.page_size]
        return PagedResult(items=items, total=total, page=query.page, page_size=query.page_size)
