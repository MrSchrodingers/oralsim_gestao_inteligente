from typing import Any

from django.utils import timezone
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository

from notification_billing.adapters.message_broker.rabbitmq import publish
from notification_billing.adapters.notifiers.registry import get_notifier
from notification_billing.core.application.commands.contact_commands import AdvanceContactStepCommand
from notification_billing.core.application.commands.notification_commands import (
    RunAutomatedNotificationsCommand,
    SendManualNotificationCommand,
)
from notification_billing.core.application.cqrs import CommandHandler, PagedResult
from notification_billing.core.application.dtos.whatsapp_notification_dto import WhatsappNotificationDTO
from notification_billing.core.application.queries.notification_queries import ListPendingSchedulesQuery
from notification_billing.core.domain.events.events import NotificationSentEvent
from notification_billing.core.domain.repositories import (
    ContactHistoryRepository,
    ContactScheduleRepository,
    FlowStepConfigRepository,
    MessageRepository,
)
from notification_billing.core.domain.services.event_dispatcher import EventDispatcher
from notification_billing.core.utils.template_utils import render_message
from plugins.django_interface.models import ContactSchedule


class NotificationSenderService:
    """
    Serviço para renderizar e enviar notificações via SMS, e-mail e WhatsApp.
    """
    def __init__(
        self,
        message_repo: MessageRepository,
        patient_repo: PatientRepository,
        installment_repo: InstallmentRepository,
    ):
        self.message_repo = message_repo
        self.patient_repo = patient_repo
        self.installment_repo = installment_repo

    def _render_content(self, msg, patient, inst) -> str:
        context = {
            "nome": patient.name,
            "valor": f"R$ {inst.installment_amount:.2f}",
            "vencimento": inst.due_date.strftime("%d/%m/%Y"),
        }
        return render_message(msg.content, context)

    def send(self, msg, patient, inst) -> None:
        content = self._render_content(msg, patient, inst)
        notifier = get_notifier(msg.type)

        if msg.type == "email":
            notifier.send(
                recipients=[patient.email],
                subject=content[:50],
                html=content,
            )
        elif msg.type == "sms":
            notifier.send(
                phones=[patient.phones[0].phone_number],
                message=content,
            )
        elif msg.type == "whatsapp":
            dto = WhatsappNotificationDTO(
                to=str(patient.phones[0].phone_number),
                message=content,
            )
            notifier.send(dto)
        else:
            raise NotImplementedError(f"Canal de notificação não suportado: {msg.type}")


class SendManualNotificationHandler(
    CommandHandler[SendManualNotificationCommand]
):
    def __init__(
        self,
        schedule_repo: ContactScheduleRepository,
        history_repo: ContactHistoryRepository,
        notification_service: NotificationSenderService,
        dispatcher: EventDispatcher,
    ):
        self.schedule_repo = schedule_repo
        self.history_repo = history_repo
        self.notification_service = notification_service
        self.dispatcher = dispatcher

    @publish(exchange="notifications", routing_key="manual")
    def handle(self, cmd: SendManualNotificationCommand) -> dict[str, Any]:
        sched = self.schedule_repo.get_by_patient_contract(
            cmd.patient_id, cmd.contract_id
        )
        inst = self.notification_service.installment_repo.get_current_installment(
            sched.contract_id
        )
        if not inst:                    
            raise ValueError(
                f"Parcela atual não encontrada para contrato {sched.contract_id}"
            )

        msg = self.notification_service.message_repo.get_message(
            cmd.channel, sched.current_step, sched.clinic_id
        )
        patient = self.notification_service.patient_repo.find_by_id(str(sched.patient_id))
        self.notification_service.send(msg, patient, inst)

        hist = self.history_repo.save_from_schedule(
            schedule=sched,
            sent_at=timezone.now(),
            success=True,
            channel=cmd.channel,
            feedback=None,
            observation="manual send",
            message=msg,
        )
        import structlog
        structlog.get_logger(__name__).info("history saved", history=hist)
        self.dispatcher.dispatch(
            NotificationSentEvent(
                schedule_id=sched.id,
                message_id=msg.id,
                sent_at=hist.sent_at,
                channel=cmd.channel,
            )
        )

        return {
            "patient_id": cmd.patient_id,
            "contract_id": cmd.contract_id,
            "channel": cmd.channel,
            "message_id": msg.id,
            "sent_at": hist.sent_at.isoformat(),
        }


class RunAutomatedNotificationsHandler(
    CommandHandler[RunAutomatedNotificationsCommand]
):
    def __init__( # noqa
        self,
        schedule_repo: ContactScheduleRepository,
        history_repo: ContactHistoryRepository,
        config_repo: FlowStepConfigRepository,
        notification_service: NotificationSenderService,
        dispatcher: EventDispatcher,
        query_bus: Any,
    ):
        self.schedule_repo = schedule_repo
        self.history_repo = history_repo
        self.config_repo = config_repo
        self.notification_service = notification_service
        self.dispatcher = dispatcher
        self.query_bus = query_bus

    @publish(exchange="notifications", routing_key="automated")
    def handle(self, cmd: RunAutomatedNotificationsCommand) -> dict[str, Any]:
        filters = {"clinic_id": cmd.clinic_id}
        if cmd.only_pending:
            filters["status"] = ContactSchedule.Status.PENDING

        query = ListPendingSchedulesQuery(
            filtros=filters, page=1, page_size=cmd.batch_size
        )
        schedules: PagedResult[Any] = self.query_bus.dispatch(query)
        now = timezone.now()
        results: list[dict[str, Any]] = []

        if not schedules.items:
            return {"clinic_id": cmd.clinic_id, "processed": 0, "results": results}

        for sched in schedules.items:
            # obtém parcela atual e paciente
            inst_page = self.notification_service.installment_repo.list_overdue(
                contract_id=sched.contract_id,
                min_days_overdue=0,
                offset=0,
                limit=1,
            )
            if not inst_page.items:
                continue
            inst = inst_page.items[0]
            if inst.received:
                continue

            patient = self.notification_service.patient_repo.find_by_id(
                sched.patient_id
            )

            # busca canais configurados no FlowStepConfig
            cfg = self.config_repo.find_by_step(sched.current_step)
            if not cfg or not cfg.active:
                continue

            for channel in cfg.channels:
                msg = self.notification_service.message_repo.get_message(
                    channel, sched.current_step, sched.clinic_id
                )
                if not msg:
                    continue

                try:
                    self.notification_service.send(msg, patient, inst)
                    success = True
                except Exception as err:
                    success = False
                    err_msg = str(err)

                hist = self.history_repo.save_from_schedule(
                    schedule=sched,
                    sent_at=now,
                    success=success,
                    channel=channel, 
                    feedback=None,
                    observation=("automated send" if success else f"error: {err_msg}"),
                    message=msg,
                )

                if success:
                    self.dispatcher.dispatch(
                        NotificationSentEvent(
                            schedule_id=sched.id,
                            message_id=msg.id,
                            sent_at=hist.sent_at,
                            channel=channel,
                        )
                    )
                results.append({
                    "patient_id": str(sched.patient_id),
                    "contract_id": str(sched.contract_id),
                    "step": sched.current_step,
                    "channel": channel,
                    "success": success,
                })

            # Avança step se ao menos um canal teve sucesso
            if any(r["success"] for r in results if r["step"] == sched.current_step and r["patient_id"] == str(sched.patient_id)):
                self.dispatcher.dispatch(
                    AdvanceContactStepCommand(schedule_id=sched.id)
                )

        return {
            "clinic_id": cmd.clinic_id,
            "processed": len(results),
            "results": results,
        }
