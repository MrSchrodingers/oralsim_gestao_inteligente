import structlog

from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ
from notification_billing.core.application.cqrs import PaginatedQueryDTO, QueryHandler
from notification_billing.core.application.queries.contact_history_queries import GetContactHistoryQuery, ListContactHistoryQuery
from notification_billing.core.application.services.oralsin_payload_builder import build_oralsin_payload
from notification_billing.core.domain.events.contact_history_events import ContactHistoryCreated
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from plugins.django_interface.models import ContactHistory


class ListContactHistoryHandler(QueryHandler[ListContactHistoryQuery, PaginatedQueryDTO]):
    # MODIFICAÇÃO: Receba o repositório por injeção de dependência
    def __init__(self, repo: ContactHistoryRepository):
        self._repo = repo

    def handle(self, query: ListContactHistoryQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetContactHistoryHandler(QueryHandler[GetContactHistoryQuery, object]):
    # MODIFICAÇÃO: Receba o repositório por injeção de dependência
    def __init__(self, repo: ContactHistoryRepository):
        self._repo = repo

    def handle(self, query: GetContactHistoryQuery):
        return self._repo.find_by_id(query.id)

# (O PublishContactHistoryToQueueHandler permanece o mesmo)
class PublishContactHistoryToQueueHandler:
    """
    Handler para o evento ContactHistoryCreated.
    Publica o histórico de contato na fila do RabbitMQ para integração com a API Oralsin.
    """
    def __init__(self, rabbit: RabbitMQ):
        self.rabbit = rabbit
        self.log = structlog.get_logger(__name__)
        self._exchange = "oralsin.activities"
        self._routing_key = "acordo_fechado"

    def __call__(self, event: ContactHistoryCreated) -> None:
        """
        Executa a lógica do handler quando o evento é disparado.
        """
        try:
            history = ContactHistory.objects.get(id=event.entity_id)
            dto = build_oralsin_payload(history)
            payload = dto.model_dump_json(by_alias=True, exclude_none=True)

            self.rabbit.channel().basic_publish(
                exchange=self._exchange,
                routing_key=self._routing_key,
                body=payload,
                properties=self.rabbit.persistent_props,
            )
            self.log.info("contact_history.enqueued", history_id=history.id)
        except ContactHistory.DoesNotExist:
            self.log.error(
                "contact_history.publish_failed",
                reason="History not found",
                history_id=event.entity_id,
            )
        except Exception as e:
            self.log.error(
                "contact_history.publish_failed",
                history_id=event.entity_id,
                error=str(e),
                exc_info=True,
            )