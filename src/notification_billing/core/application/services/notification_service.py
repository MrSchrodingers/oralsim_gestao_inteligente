from typing import Protocol

import structlog

from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ
from notification_billing.core.application.commands.notification_commands import (
    RunAutomatedNotificationsCommand,
    SendManualNotificationCommand,
)
from notification_billing.core.application.cqrs import CommandBus, QueryBus
from notification_billing.core.domain.repositories.contact_schedule_repository import (
    ContactScheduleRepository,
)
from plugins.django_interface.models import ContactSchedule

logger = structlog.get_logger(__name__)


class _AutomatedHandlerProto(Protocol):
    """Protocolo mínimo para reusar _process_schedule()."""

    def _process_schedule(self, schedule: ContactSchedule) -> dict | None: ...


class NotificationFacadeService:
    """
    Fachada simplificada chamada pelos consumers RabbitMQ.

    - Mantém a API anterior (`send_manual`, `run_automated`)
    - Acrescenta:
        • `enqueue_pending_schedules()`  – produtor (explode em jobs por schedule)
        • `process_single_schedule()`    – consumidor de um único job
    """

    def __init__(  # noqa: PLR0913
        self,
        command_bus: CommandBus,
        query_bus: QueryBus,
        schedule_repo: ContactScheduleRepository,
        rabbit: RabbitMQ,
        automated_handler: _AutomatedHandlerProto,
    ) -> None:
        self.commands = command_bus
        self.queries = query_bus
        self.schedule_repo = schedule_repo
        self.rabbit = rabbit
        self._automated_handler = automated_handler

    # ------------------------------------------------ manual
    def send_manual(
        self,
        patient_id: str,
        contract_id: str,
        channel: str,
        message_id: str | None = None,
    ) -> None:
        self.commands.dispatch(
            SendManualNotificationCommand(
                patient_id=patient_id,
                contract_id=contract_id,
                channel=channel,
                message_id=message_id,
            )
        )

    # ------------------------------------------------ lote automático (pai)
    def run_automated(self, clinic_id: str, batch_size: int = 10) -> None:
        self.commands.dispatch(
            RunAutomatedNotificationsCommand(
                clinic_id=clinic_id,
                batch_size=batch_size,
            )
        )

    # ------------------------------------------------ novos helpers
    def enqueue_pending_schedules(self, clinic_id: str) -> None:
        """
        Percorre pendências e publica **uma mensagem por schedule**.

        Cada mensagem vai parar na fila `notifications.schedule`.
        """
        for sch in self.schedule_repo.stream_pending(
            clinic_id=clinic_id, only_pending=True, chunk_size=500
        ):
            self.rabbit.publish(
                "notifications",
                "schedule",
                {"schedule_id": str(sch.id)},
            )

    def process_single_schedule(self, schedule_id: str) -> None:
        """
        Executa um agendamento isolado, reaproveitando a lógica do handler.
        """
        try:
            sch = ContactSchedule.objects.get(id=schedule_id)
        except ContactSchedule.DoesNotExist:
            logger.warning("schedule.not_found", id=schedule_id)
            return

        self._automated_handler._process_schedule(sch)
