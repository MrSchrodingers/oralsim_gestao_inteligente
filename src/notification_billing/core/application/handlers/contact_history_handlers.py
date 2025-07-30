from notification_billing.core.application.cqrs import PaginatedQueryDTO, QueryHandler
from notification_billing.core.application.queries.contact_history_queries import GetContactHistoryQuery, ListContactHistoryQuery
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository


class ListContactHistoryHandler(QueryHandler[ListContactHistoryQuery, PaginatedQueryDTO]):
    def __init__(self, repo: ContactHistoryRepository):
        self._repo = repo

    def handle(self, query: ListContactHistoryQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetContactHistoryHandler(QueryHandler[GetContactHistoryQuery, object]):
    def __init__(self, repo: ContactHistoryRepository):
        self._repo = repo

    def handle(self, query: GetContactHistoryQuery):
        return self._repo.find_by_id(query.id)