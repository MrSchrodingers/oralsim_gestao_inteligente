# 13 Payment Methods
from notification_billing.adapters.repositories.flow_step_config_repo_impl import FlowStepConfigRepoImpl
from notification_billing.core.application.cqrs import PaginatedQueryDTO, QueryHandler
from notification_billing.core.application.queries.flow_step_config_queries import GetFlowStepConfigQuery, ListFlowStepConfigsQuery


class ListFlowStepConfigHandler(QueryHandler[ListFlowStepConfigsQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = FlowStepConfigRepoImpl()

    def handle(self, query: ListFlowStepConfigsQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetFlowStepConfigHandler(QueryHandler[GetFlowStepConfigQuery, object]):
    def __init__(self):
        self._repo = FlowStepConfigRepoImpl()

    def handle(self, query: GetFlowStepConfigQuery):
        return self._repo.find_by_id(query.payment_method_id)