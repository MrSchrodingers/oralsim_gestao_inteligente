from datetime import datetime
from typing import Any

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
from notification_billing.core.domain.events.events import NotificationScheduledEvent, NotificationSentEvent
from notification_billing.core.domain.repositories import (
    ContactHistoryRepository,
    ContactScheduleRepository,
)
from notification_billing.core.domain.services.event_dispatcher import EventDispatcher


class AdvanceContactStepHandler(CommandHandler[AdvanceContactStepCommand]):
    def __init__(
        self,
        schedule_repo: ContactScheduleRepository,
        dispatcher: EventDispatcher,
    ):
        self.schedule_repo = schedule_repo
        self.dispatcher = dispatcher

    def handle(self, cmd: AdvanceContactStepCommand) -> Any:
        sched = self.schedule_repo.advance_contact_step(cmd.schedule_id)
        # só dispara se realmente houver próximo step
        if sched:
            self.dispatcher.dispatch(
                NotificationScheduledEvent(
                    schedule_id=sched.id,
                    patient_id=sched.patient_id,
                    contract_id=sched.contract_id,
                    step=sched.current_step,
                    channel=sched.channel,
                    scheduled_date=sched.scheduled_date,
                )
            )
        return sched


class RecordContactSentHandler(CommandHandler[RecordContactSentCommand]):
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

        # registra no histórico
        hist = self.history_repo.save_from_schedule(
            schedule=sched,
            sent_at=datetime.utcnow(),
            success=cmd.success,
            feedback=cmd.feedback_status,
            observation=cmd.observation,
        )
        # dispara evento de envio
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
    def __init__(self, schedule_repo: ContactScheduleRepository):
        self.repo = schedule_repo

    def handle(self, query: ListDueContactsQuery) -> PagedResult[Any]:
        filtros = query.filtros or {}
        clinic_id = filtros.get("clinic_id")
        req = get_current_request()
        if not clinic_id and req and getattr(req.user, "role", None) == "clinic":
            clinic_id = getattr(req.user, "clinic_id", None)
            
        return self.repo.list_due(
            clinic_id=clinic_id,
            now=datetime.utcnow(),
            offset=(query.page - 1) * query.page_size,
            limit=query.page_size,
        )
