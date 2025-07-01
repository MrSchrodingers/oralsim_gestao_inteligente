"""
🛠  Ajustes para suportar «phonecall» criando PendingCall em vez de
tentar disparar uma chamada automática.

▪ O NotificationSenderService continua responsável apenas por disparos
  “reais” (email, sms, whatsapp).  
▪ Quando o canal do step é "phonecall", criamos uma entrada em
  PendingCallRepository e **não** bloqueamos o restante do fluxo.
"""

import time
from typing import Any

from django.utils import timezone
from oralsin_core.adapters.observability.metrics import NOTIFICATIONS_SENT
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import (
    InstallmentRepository,
)
from oralsin_core.core.domain.repositories.patient_repository import (
    PatientRepository,
)

from notification_billing.adapters.message_broker.rabbitmq import publish
from notification_billing.adapters.notifiers.registry import get_notifier
from notification_billing.adapters.observability.metrics import (
    NOTIFICATION_FLOW_COUNT,
    NOTIFICATION_FLOW_DURATION,
)
from notification_billing.core.application.commands.contact_commands import (
    AdvanceContactStepCommand,
)
from notification_billing.core.application.commands.notification_commands import (
    RunAutomatedNotificationsCommand,
    SendManualNotificationCommand,
)
from notification_billing.core.application.cqrs import CommandBus, CommandHandler, PagedResult
from notification_billing.core.application.dtos.whatsapp_notification_dto import (
    WhatsappNotificationDTO,
)
from notification_billing.core.application.queries.notification_queries import (
    ListPendingSchedulesQuery,
)
from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity
from notification_billing.core.domain.events.events import NotificationSentEvent
from notification_billing.core.domain.repositories import (
    ContactHistoryRepository,
    ContactScheduleRepository,
    FlowStepConfigRepository,
    MessageRepository,
)
from notification_billing.core.domain.repositories.pending_call_repository import (
    PendingCallRepository,
)
from notification_billing.core.domain.services.event_dispatcher import EventDispatcher
from notification_billing.core.utils.template_utils import render_message
from plugins.django_interface.models import ContactSchedule, FlowStepConfig


# ──────────────────────────────────────────────────────────────────────────
# Service de envio (somente canais “automáticos”)
# ──────────────────────────────────────────────────────────────────────────
class NotificationSenderService:
    """
    Renderiza e envia notificações via e-mail, SMS ou WhatsApp.
    (phonecall é tratado fora – cria PendingCall.)
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

    # ------------------------------------------------------------------ #
    def _render_content(self, msg, patient, inst) -> str:
        ctx = {
            "nome": patient.name,
            "valor": f"R$ {inst.installment_amount:.2f}",
            "vencimento": inst.due_date.strftime("%d/%m/%Y"),
        }
        return render_message(msg.content, ctx)

    # ------------------------------------------------------------------ #
    def send(self, msg, patient, inst) -> None:
        content = self._render_content(msg, patient, inst)
        notifier = get_notifier(msg.type)

        if msg.type == "email":
            notifier.send(recipients=[patient.email], subject="Notificaão de Atraso de Parcelas.", html=content)
        elif msg.type == "sms":
            notifier.send(phones=[patient.phones[0].phone_number], message=content)
        elif msg.type == "whatsapp":
            dto = WhatsappNotificationDTO(
                to=str(patient.phones[0].phone_number), message=content
            )
            notifier.send(dto)
        else:
            raise NotImplementedError(f"Canal não suportado: {msg.type}")


# ──────────────────────────────────────────────────────────────────────────
# Handler – disparo manual
# ──────────────────────────────────────────────────────────────────────────
class SendManualNotificationHandler(CommandHandler[SendManualNotificationCommand]):
    def __init__(  # noqa: PLR0913
        self,
        schedule_repo: ContactScheduleRepository,
        history_repo: ContactHistoryRepository,
        notification_service: NotificationSenderService,
        contract_repo: ContractRepository,
        dispatcher: EventDispatcher,
        pending_call_repo: PendingCallRepository,
    ):
        self.schedule_repo = schedule_repo
        self.history_repo = history_repo
        self.notification_service = notification_service
        self.dispatcher = dispatcher
        self.contract_repo = contract_repo
        self.pending_call_repo = pending_call_repo

    # ------------------------------------------------------------------ #
    @publish(exchange="notifications", routing_key="manual")
    def handle(self, cmd: SendManualNotificationCommand) -> dict[str, Any]:
        start = time.perf_counter()
        success = True
        try:
            sched = self.schedule_repo.get_by_patient_contract(
                cmd.patient_id, cmd.contract_id
            )
            contract = self.contract_repo.find_by_id(sched.contract_id)
            if not contract or not contract.do_notifications:
                # pula todo o fluxo de notificação
                raise ValueError(
                    f"Paciente sem permissão para notificação {contract.patient_id}"
                )
                
            inst = self.notification_service.installment_repo.get_current_installment(
                sched.contract_id
            )
            if not inst:
                raise ValueError(
                    f"Parcela atual não encontrada para contrato {sched.contract_id}"
                )

            # phonecall → cria pendência em vez de enviar
            if cmd.channel == "phonecall":
                self.pending_call_repo.create(
                    patient_id=sched.patient_id,
                    contract_id=sched.contract_id,
                    clinic_id=sched.clinic_id,
                    schedule_id=sched.id,
                    current_step=sched.current_step,
                    scheduled_at=sched.scheduled_date or timezone.now(),
                )
                sent_hist = None  # não há envio “de fato”
            else:
                msg = self.notification_service.message_repo.get_message(
                    cmd.channel, sched.current_step, sched.clinic_id
                )
                patient = self.notification_service.patient_repo.find_by_id(
                    str(sched.patient_id)
                )
                self.notification_service.send(msg, patient, inst)

                sent_hist = self.history_repo.save_from_schedule(
                    schedule=sched,
                    sent_at=timezone.now(),
                    success=True,
                    channel=cmd.channel,
                    feedback=None,
                    observation="manual send",
                    message=msg,
                )
                self.dispatcher.dispatch(
                    NotificationSentEvent(
                        schedule_id=sched.id,
                        message_id=msg.id,
                        sent_at=sent_hist.sent_at,
                        channel=cmd.channel,
                    )
                )

            return {
                "patient_id": cmd.patient_id,
                "contract_id": cmd.contract_id,
                "channel": cmd.channel,
                "message_id": getattr(sent_hist, "message_id", None),
                "sent_at": getattr(sent_hist, "sent_at", None)
                and sent_hist.sent_at.isoformat(),
            }
        except Exception:
            success = False
            raise
        finally:
            NOTIFICATIONS_SENT.labels("manual", cmd.channel, str(success)).inc()
            NOTIFICATION_FLOW_COUNT.labels("manual", str(success)).inc()
            NOTIFICATION_FLOW_DURATION.labels("manual").observe(
                time.perf_counter() - start
            )


# ──────────────────────────────────────────────────────────────────────────
# Handler – disparo automático (batch)
# ──────────────────────────────────────────────────────────────────────────
class RunAutomatedNotificationsHandler(CommandHandler[RunAutomatedNotificationsCommand]):
    def __init__(  # noqa: PLR0913
        self,
        schedule_repo: ContactScheduleRepository,
        history_repo: ContactHistoryRepository,
        config_repo: FlowStepConfigRepository,
        notification_service: NotificationSenderService,
        pending_call_repo: PendingCallRepository,
        patient_repo: PatientRepository,
        message_repo: MessageRepository,
        contract_repo: ContractRepository,
        dispatcher: EventDispatcher,
        query_bus: Any,
        command_bus: CommandBus,
    ):
        self.schedule_repo = schedule_repo
        self.history_repo = history_repo
        self.config_repo = config_repo
        self.patient_repo = patient_repo
        self.message_repo = message_repo
        self.notification_service = notification_service
        self.pending_call_repo = pending_call_repo
        self.contract_repo = contract_repo
        self.dispatcher = dispatcher
        self.query_bus = query_bus
        self.command_bus = command_bus

    @publish(exchange="notifications", routing_key="automated")
    def handle(self, cmd: RunAutomatedNotificationsCommand) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
        start = time.perf_counter()
        success = True
        try:
            # 1) Recupera todos os agendamentos pendentes
            filters = {"clinic_id": cmd.clinic_id}
            if cmd.only_pending:
                filters["status"] = ContactSchedule.Status.PENDING

            query = ListPendingSchedulesQuery(
                filtros=filters, page=1, page_size=cmd.batch_size
            )
            schedules: PagedResult[ContactScheduleEntity] = self.query_bus.dispatch(query)
            now = timezone.now()
            results: list[dict[str, Any]] = []

            if not schedules.items:
                return {"clinic_id": cmd.clinic_id, "processed": 0, "results": results}

            # 2) Processa cada schedule individualmente
            for sched in schedules.items:
                # a) valida parcela
                if not sched.installment_id:
                    continue
                inst = self.schedule_repo.installment_repo.find_by_id(sched.installment_id)
                if not inst or inst.received:
                    continue

                # b) valida contrato e permissão de notificação
                contract = self.contract_repo.find_by_id(sched.contract_id)
                if not contract or not contract.do_notifications:
                    continue

                patient = self.patient_repo.find_by_id(sched.patient_id)

                # c) valida step ativo
                cfg = self.config_repo.find_by_step(sched.current_step)
                if not cfg or not cfg.active:
                    continue

                # d) só considera o canal que veio no próprio schedule
                channel = sched.channel

                # e) se for phonecall, só cria pendência
                if channel == FlowStepConfig.Channel.PHONECALL:
                    self.pending_call_repo.create(
                        patient_id=sched.patient_id,
                        contract_id=sched.contract_id,
                        clinic_id=sched.clinic_id,
                        schedule_id=sched.id,
                        current_step=sched.current_step,
                        scheduled_at=sched.scheduled_date or now,
                    )
                    results.append({
                        "patient_id": str(sched.patient_id),
                        "contract_id": str(sched.contract_id),
                        "step": sched.current_step,
                        "channel": channel,
                        "success": True,
                        "pending_call": True,
                    })
                    continue

                # f) demais canais: busca template e envia
                msg = self.message_repo.get_message(
                    channel, sched.current_step, sched.clinic_id
                )
                if not msg:
                    continue

                try:
                    self.notification_service.send(msg, patient, inst)
                    send_ok = True
                except Exception as err:
                    send_ok = False
                    err_msg = str(err)

                # g) grava histórico e dispara evento
                hist = self.history_repo.save_from_schedule(
                    schedule=sched,
                    sent_at=now,
                    success=send_ok,
                    channel=channel,
                    feedback=None,
                    observation="automated send" if send_ok else f"error: {err_msg}",
                    message=msg,
                )
                NOTIFICATIONS_SENT.labels("automated", channel, str(send_ok)).inc()

                if send_ok:
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
                    "success": send_ok,
                })

                # h) avança o fluxo se enviou com sucesso
                if send_ok:
                    self.command_bus.dispatch(
                        AdvanceContactStepCommand(schedule_id=str(sched.id))
                    )

            return {
                "clinic_id": cmd.clinic_id,
                "processed": len(results),
                "results": results,
            }

        except Exception:
            success = False
            raise
        finally:
            NOTIFICATION_FLOW_COUNT.labels("automated", str(success)).inc()
            NOTIFICATION_FLOW_DURATION.labels("automated").observe(
                time.perf_counter() - start
            )
