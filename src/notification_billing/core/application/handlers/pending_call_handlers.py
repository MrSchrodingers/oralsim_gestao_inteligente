from __future__ import annotations

from datetime import datetime

from oralsin_core.core.application.cqrs import CommandHandler, PagedResult, QueryHandler

from notification_billing.core.domain.entities.pending_call_entity import PendingCallEntity
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from notification_billing.core.domain.repositories.contact_schedule_repository import ContactScheduleRepository
from notification_billing.core.domain.repositories.pending_call_repository import PendingCallRepository

from ..commands.pending_call_commands import SetPendingCallDoneCommand
from ..queries.pending_call_queries import GetPendingCallQuery, ListPendingCallsQuery


class ListPendingCallsHandler(QueryHandler[ListPendingCallsQuery, PagedResult[PendingCallEntity]]):
    def __init__(self, repo: PendingCallRepository):
        self.repo = repo

    def handle(self, q: ListPendingCallsQuery) -> PagedResult[PendingCallEntity]:
        return self.repo.list(q.filtros, q.page, q.page_size)


class GetPendingCallHandler(QueryHandler[GetPendingCallQuery, PendingCallEntity | None]):
    def __init__(self, repo: PendingCallRepository):
        self.repo = repo

    def handle(self, q: GetPendingCallQuery) -> PendingCallEntity | None:
        filtros = dict(q.filtros)
        filtros["id"] = q.id
        pr: PagedResult[PendingCallEntity] = self.repo.list(filtros, page=1, page_size=1)
        return pr.items[0] if pr.items else None


class SetPendingCallDoneHandler(CommandHandler[SetPendingCallDoneCommand]):
    def __init__(self, repo: PendingCallRepository, history_repo: ContactHistoryRepository,
        schedule_repo: ContactScheduleRepository, logger, dispatcher):
        self.repo = repo
        self.history_repo = history_repo
        self.schedule_repo = schedule_repo
        self.dispatcher = dispatcher
        self.logger = logger

    def handle(self, cmd: SetPendingCallDoneCommand) -> None:
        self.repo.set_done(cmd.call_id, cmd.success, cmd.notes)
        
        sched_id = self.repo.find_by_id(cmd.call_id).schedule_id
        
        sched_entity = self.schedule_repo.find_by_id(sched_id)
        # Registra no histórico de contato
        if sched_entity:
            sent_at = datetime.utcnow()
            self.history_repo.save_from_schedule(
                schedule=sched_entity,
                sent_at=sent_at,
                success=cmd.success,
                channel="phonecall",
                feedback=None,
                observation=cmd.notes,
                message=None,
            )
            
        # disparar evento de domínio de resolução de pendência
        from notification_billing.core.domain.events.events import PendingCallResolvedEvent  # noqa: PLC0415

        self.dispatcher.dispatch(
            PendingCallResolvedEvent(
                call_id=cmd.call_id,
                success=cmd.success,
                user_id=cmd.user_id,
                resolved_at=datetime.utcnow(),
            )
        )