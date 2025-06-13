from oralsin_core.core.application.cqrs import PaginatedQueryDTO, QueryHandler

from cordial_billing.adapters.repositories.collection_case_repo_impl import CollectionCaseRepoImpl
from cordial_billing.core.application.queries.collection_case_queries import GetCollectionCaseQuery, ListCollectionCasesQuery


class ListCollectionCaseHandler(QueryHandler[ListCollectionCasesQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = CollectionCaseRepoImpl()

    def handle(self, query: ListCollectionCasesQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetCollectionCaseHandler(QueryHandler[GetCollectionCaseQuery, object]):
    def __init__(self):
        self._repo = CollectionCaseRepoImpl()

    def handle(self, query: GetCollectionCaseQuery):
        return self._repo.find_by_id(query.collection_case_id)
    
