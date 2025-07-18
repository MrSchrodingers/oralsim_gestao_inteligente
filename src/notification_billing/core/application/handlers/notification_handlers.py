import time
from typing import Any

import structlog
from django.db import DatabaseError, transaction
from django.utils import timezone
from oralsin_core.core.domain.repositories.contract_repository import (
    ContractRepository,
)
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
from notification_billing.core.application.cqrs import (
    CommandBus,
    CommandHandler,
)
from notification_billing.core.application.dtos.whatsapp_notification_dto import (
    WhatsappNotificationDTO,
)
from notification_billing.core.domain.entities.contact_schedule_entity import (
    ContactScheduleEntity,
)
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
from notification_billing.core.domain.services.event_dispatcher import (
    EventDispatcher,
)
from notification_billing.core.utils.template_utils import render_message
from plugins.django_interface.models import ContactHistory, ContactSchedule, FlowStepConfig

logger = structlog.get_logger(__name__)

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
    
    def _channels_for_step(self, schedule: ContactSchedule) -> list[str]:
        cfg = FlowStepConfig.objects.get(step_number=schedule.current_step)
        return [c for c in cfg.channels if c not in ("letter", "pending_call")]

    def _send_channel(self, schedule: ContactSchedule, channel: str) -> bool:
        """Envia mensagem e devolve True/False (sucesso)."""
        try:
            return self._dispatcher.send(schedule, channel)
        except Exception:
            return False
    # ------------------------------------------------------------------ #
    def send(self, msg, patient, inst) -> None:
        content = self._render_content(msg, patient, inst)
        notifier = get_notifier(msg.type)

        if msg.type == "email":
            notifier.send(
                recipients=[patient.email],
                subject="Notificação de Atraso de Parcelas.",
                html=content,
            )
        elif msg.type == "sms":
            notifier.send(
                phones=[patient.phones[0].phone_number], message=content
            )
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
class SendManualNotificationHandler(
    CommandHandler[SendManualNotificationCommand]
):
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

            inst = (
                self.notification_service.installment_repo.get_current_installment(
                    sched.contract_id
                )
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
            NOTIFICATION_FLOW_COUNT.labels("manual", str(success)).inc()
            NOTIFICATION_FLOW_DURATION.labels("manual").observe(
                time.perf_counter() - start
            )


# ──────────────────────────────────────────────────────────────────────────
# Handler – disparo automático (batch)
# ──────────────────────────────────────────────────────────────────────────
class RunAutomatedNotificationsHandler(
    CommandHandler[RunAutomatedNotificationsCommand]
):
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

    def _process_schedule(self, schedule: ContactSchedule) -> dict[str, Any] | None:
        """
        Executa **1** agendamento inteiro (todos os canais),
        garantindo idempotência e tratamento de falhas.
        """
        try:
            with transaction.atomic():
                # 1) marca como PROCESSING e obtém lock pessimista
                locked = (
                    ContactSchedule.objects
                    .select_for_update(skip_locked=True)
                    .get(id=schedule.id, status=ContactSchedule.Status.PENDING)
                )
                locked.status = ContactSchedule.Status.PROCESSING
                locked.save(update_fields=["status", "updated_at"])

            # 2) fora da transação, faz os envios (pode demorar)
            results: dict[str, bool] = {}
            for channel in self.notification_service._channels_for_step(locked):
                if channel == "phonecall":
                    self.pending_call_repo.create(
                        patient_id=locked.patient_id,
                        contract_id=locked.contract_id,
                        clinic_id=locked.clinic_id,
                        schedule_id=locked.id,
                        current_step=locked.current_step,
                        scheduled_at=locked.scheduled_date or timezone.now(),
                    )
                    results[channel] = True
                    continue
                ok = self._send_through_notifier(locked, channel)
                results[channel] = ok

            # 3) grava histórico e dá DONE numa nova transação
            with transaction.atomic():
                # idempotente – UNIQUE no ContactHistory garante
                for channel, ok in results.items():
                    ContactHistory.objects.get_or_create(
                        schedule=locked,
                        contact_type=channel,
                        advance_flow=locked.advance_flow,
                        defaults=dict(
                            patient=locked.patient,
                            contract=locked.contract,
                            clinic=locked.clinic,
                            sent_at=timezone.now(),
                            success=ok,
                        ),
                    )

                locked.status = (
                    ContactSchedule.Status.REJECTED
                    if not all(results.values())
                    else ContactSchedule.Status.APPROVED
                )
                locked.save(update_fields=["status", "updated_at"])
                
            return {"schedule_id": str(schedule.id), "results": results}

        except DatabaseError:
            logger.warning("schedule.lock_failed", id=schedule.id)
            return None
        except Exception:
            logger.exception("schedule.unhandled_error", id=schedule.id)
            return None

    def _handle_phonecall(
        self, sched: ContactScheduleEntity, now: timezone
    ) -> dict[str, Any]:
        """Cria uma pendência de chamada telefônica."""
        self.pending_call_repo.create(
            patient_id=sched.patient_id,
            contract_id=sched.contract_id,
            clinic_id=sched.clinic_id,
            schedule_id=sched.id,
            current_step=sched.current_step,
            scheduled_at=sched.scheduled_date or now,
        )
        return self._build_result(sched, success=True, pending_calls=True)

    def _handle_notification(
        self, sched: ContactScheduleEntity, patient, inst, now: timezone
    ) -> dict[str, Any]:
        """Envia uma notificação (email, sms, whatsapp)."""
        msg = self.message_repo.get_message(
            sched.channel, sched.current_step, sched.clinic_id
        )
        if not msg:
            return self._build_result(sched, success=False, error="Mensagem não encontrada")

        try:
            self.notification_service.send(msg, patient, inst)
            send_ok = True
            error_msg = None
        except Exception as err:
            send_ok = False
            error_msg = str(err)

        self._record_history(sched, msg, now, send_ok, error_msg)
        if send_ok:
            self._dispatch_event(sched, msg, now)
            self._advance_step(sched)

        return self._build_result(sched, success=send_ok, error=error_msg)

    def _record_history(
        self, sched: ContactScheduleEntity, msg, now, success, error_msg=None
    ):
        """Salva o histórico de contato."""
        observation = (
            "automated send"
            if success
            else f"error: {error_msg}"
        )
        self.history_repo.save_from_schedule(
            schedule=sched,
            sent_at=now,
            success=success,
            channel=sched.channel,
            feedback=None,
            observation=observation,
            message=msg,
        )

    def _dispatch_event(self, sched: ContactScheduleEntity, msg, now: timezone):
        """Dispara o evento de notificação enviada."""
        self.dispatcher.dispatch(
            NotificationSentEvent(
                schedule_id=sched.id,
                message_id=msg.id,
                sent_at=now,
                channel=sched.channel,
            )
        )

    def _advance_step(self, sched: ContactScheduleEntity):
        """Avança para a próxima etapa do fluxo."""
        self.command_bus.dispatch(
            AdvanceContactStepCommand(schedule_id=str(sched.id))
        )

    def _build_result(self, sched, success, error=None, pending_calls=False):
        """Constrói o dicionário de resultado para um agendamento."""
        return {
            "patient_id": str(sched.patient_id),
            "contract_id": str(sched.contract_id),
            "step": sched.current_step,
            "channel": sched.channel,
            "success": success,
            "error": error,
            "pending_calls": pending_calls,
        }

    @publish(exchange="notifications", routing_key="automated")
    def handle(
        self, cmd: RunAutomatedNotificationsCommand
    ) -> dict[str, Any]:
        start = time.perf_counter()
        success = True
        try:
            _now = timezone.now()
            processed = 0
            results: list[dict[str, Any]] = []

            for sched in self.schedule_repo.stream_pending(
                clinic_id=cmd.clinic_id,
                only_pending=cmd.only_pending,
                chunk_size=cmd.batch_size,
            ):
                result = self._process_schedule(sched)  
                if result is not None:
                    results.append(result)
                processed += 1

            if processed == 0:
                return {"clinic_id": cmd.clinic_id, "processed": 0, "results": results}
 

            return {
                "clinic_id": cmd.clinic_id,
                "processed": processed,
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
            
    def _send_through_notifier(self, schedule: ContactSchedule, channel: str) -> bool:
        """
        Resolvido aqui para não depender de atributo privado de NotificationSenderService.
        """
        inst = self.notification_service.installment_repo.get_current_installment(schedule.contract_id)
        if not inst:
            return False
        patient = self.notification_service.patient_repo.find_by_id(str(schedule.patient_id))
        msg = self.message_repo.get_message(channel, schedule.current_step, schedule.clinic_id)
        if not (patient and msg and inst):
            return False
        try:
            self.notification_service.send(msg, patient, inst)
            return True
        except Exception:
            logger.exception("send_channel_failed", schedule_id=schedule.id, channel=channel)
            return False