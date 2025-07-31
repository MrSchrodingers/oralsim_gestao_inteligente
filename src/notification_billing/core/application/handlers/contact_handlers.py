from datetime import datetime
from typing import Any

from django.db import transaction
from oralsin_core.adapters.context.request_context import get_current_request

from notification_billing.core.application.commands.contact_commands import (
    AdvanceContactStepCommand,
    RecordContactSentCommand,
)
from notification_billing.core.application.cqrs import (
    CommandHandler,
    PagedResult,
    QueryHandler,
)
from notification_billing.core.application.queries.contact_queries import ListDueContactsQuery
from notification_billing.core.application.services.contact_service import ContactSchedulingService
from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity
from notification_billing.core.domain.events.events import NotificationSentEvent
from notification_billing.core.domain.repositories import (
    ContactHistoryRepository,
    ContactScheduleRepository,
)
from notification_billing.core.domain.services.event_dispatcher import EventDispatcher


class AdvanceContactStepHandler(CommandHandler[AdvanceContactStepCommand]):
    """
    Handler para avançar um contato no fluxo. Delega 100% da lógica
    de negócio para o ContactSchedulingService.
    """
    def __init__(self, scheduling_service: ContactSchedulingService):
        self.scheduling_service = scheduling_service

    @transaction.atomic
    def handle(self, cmd: AdvanceContactStepCommand) -> ContactScheduleEntity | None:
        return self.scheduling_service.advance_after_success(cmd.schedule_id)


class RecordContactSentHandler(CommandHandler[RecordContactSentCommand]):
    """
    Registra o histórico de um contato enviado.
    Esta operação é idempotente por natureza, pois sempre cria um novo registro de histórico.
    """
    def __init__(
        self,
        schedule_repo: ContactScheduleRepository,
        history_repo: ContactHistoryRepository,
        dispatcher: EventDispatcher,
    ):
        self.schedule_repo = schedule_repo
        self.history_repo = history_repo
        self.dispatcher = dispatcher

    def handle(self, cmd: RecordContactSentCommand) -> Any:
        sched = self.schedule_repo.find_by_id(cmd.schedule_id)
        if not sched:
            return None

        # Registra no histórico. datetime.utcnow() garante um timestamp único.
        hist = self.history_repo.save_from_schedule(
            schedule=sched,
            sent_at=datetime.utcnow(),
            success=cmd.success,
            feedback=cmd.feedback_status,
            observation=cmd.observation,
        )
        
        # Dispara evento de domínio para desacoplar outras ações.
        self.dispatcher.dispatch(
            NotificationSentEvent(
                schedule_id=sched.id,
                message_id=None,
                sent_at=hist.sent_at,
                channel=sched.channel,
            )
        )
        return hist


class ListDueContactsHandler(QueryHandler[ListDueContactsQuery, PagedResult[Any]]):
    """Handler para listar contatos pendentes de envio."""
    def __init__(self, schedule_repo: ContactScheduleRepository):
        self.repo = schedule_repo

    def handle(self, query: ListDueContactsQuery) -> PagedResult[Any]:
        filtros = query.filtros or {}
        req = get_current_request()
        if "clinic_id" not in filtros and req and getattr(req.user, "role", None) == "clinic":
            filtros["clinic_id"] = getattr(req.user, "clinic_id", None)
            
        filtros["status"] = "pending"
        filtros["scheduled_date__lte"] = datetime.utcnow()

        return self.repo.list(
            filtros=filtros,
            page=query.page,
            page_size=query.page_size,
        )