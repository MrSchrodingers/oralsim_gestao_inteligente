from notification_billing.adapters.repositories.message_repo_impl import MessageRepoImpl
from notification_billing.core.application.cqrs import PaginatedQueryDTO, QueryHandler
from notification_billing.core.application.queries.message_queries import GetMessageQuery, ListMessagesQuery


class ListMessagesHandler(QueryHandler[ListMessagesQuery, PaginatedQueryDTO]):
    def __init__(self):
      self._repo = MessageRepoImpl()

    def handle(self, query: ListMessagesQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetMessageHandler(QueryHandler[GetMessageQuery, object]):
    def __init__(self):
      self._repo = MessageRepoImpl()

    def handle(self, query: GetMessageQuery):
        return self._repo.find_by_id(query.message_id)
