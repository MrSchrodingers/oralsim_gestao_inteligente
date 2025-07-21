from notification_billing.adapters.repositories.contact_history_repo_impl import ContactHistoryRepoImpl
from notification_billing.core.application.cqrs import PaginatedQueryDTO, QueryHandler
from notification_billing.core.application.queries.contact_history_queries import GetContactHistoryQuery, ListContactHistoryQuery


class ListContactHistoryHandler(QueryHandler[ListContactHistoryQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = ContactHistoryRepoImpl()

    def handle(self, query: ListContactHistoryQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetContactHistoryHandler(QueryHandler[GetContactHistoryQuery, object]):
    def __init__(self):
        self._repo = ContactHistoryRepoImpl()

    def handle(self, query: GetContactHistoryQuery):
        return self._repo.find_by_id(query.id)
