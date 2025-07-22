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
from requests.exceptions import HTTPError

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
from notification_billing.core.domain.events.exceptions import NotificationError, PermanentNotificationError, TemporaryNotificationError
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
blocking_channels = {'sms', 'whatsapp', 'email'}

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
        overdue_count = self.installment_repo.count_overdue_by_contract(
            contract_id=inst.contract_id
        )
        
        ctx = {
            "nome": patient.name,
            "valor": f"R$ {inst.installment_amount:.2f}",
            "vencimento": inst.due_date.strftime("%d/%m/%Y"),
            "total_parcelas_em_atraso": overdue_count,
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

        try:
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
        except HTTPError as http_err:
            # Lógica para traduzir o erro HTTP em nossas exceções de negócio.
            status_code = http_err.response.status_code
            if 400 <= status_code < 500:  # noqa: PLR2004
                # Erros 4xx são erros do cliente (ex: Bad Request), considerados permanentes.
                raise PermanentNotificationError(f"Erro permanente do cliente (HTTP {status_code}): {http_err}") from http_err
            elif 500 <= status_code < 600:  # noqa: PLR2004
                # Erros 5xx são erros do servidor, considerados temporários.
                raise TemporaryNotificationError(f"Erro temporário no servidor do provedor (HTTP {status_code}): {http_err}") from http_err
            else:
                # Outros erros HTTP são tratados como temporários por precaução.
                raise TemporaryNotificationError(f"Erro HTTP inesperado: {http_err}") from http_err
        
        except Exception as e:
            # Captura qualquer outra exceção não-HTTP e a envolve em nossa exceção base.
            raise NotificationError(f"Erro inesperado durante o envio: {e}") from e


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

            msg = self.notification_service.message_repo.get_message(
                        locked.channel, locked.current_step, locked.clinic
                    )
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
                            message_id=msg.id if msg else None,
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
            
    def _process_schedule_group(self, representative_schedule: ContactSchedule) -> dict[str, Any] | None:
        """
        Executa um GRUPO de agendamentos para um paciente/contrato/etapa,
        enviando para cada canal apenas uma vez e avançando a etapa se bem-sucedido.
        """
        patient_id = representative_schedule.patient.id
        contract_id = representative_schedule.contract.id
        current_step = representative_schedule.current_step
        
        try:
            with transaction.atomic():
                schedules_in_group = list(
                    ContactSchedule.objects.select_for_update(skip_locked=True).filter(
                        patient_id=patient_id,
                        contract_id=contract_id,
                        current_step=current_step,
                        status=ContactSchedule.Status.PENDING,
                    )
                )

                if not schedules_in_group:
                    logger.info("schedule_group.already_locked_or_processed", patient_id=str(patient_id), contract_id=str(contract_id))
                    return None

                schedule_ids = [s.id for s in schedules_in_group]
                ContactSchedule.objects.filter(id__in=schedule_ids).update(
                    status=ContactSchedule.Status.PROCESSING,
                    updated_at=timezone.now()
                )

            results: dict[str, bool] = {}
            for schedule in schedules_in_group:
                channel = schedule.channel
                if channel == "letter":
                    continue
                
                if channel == "phonecall":
                    self.pending_call_repo.create(
                        patient_id=schedule.patient.id,
                        contract_id=schedule.contract.id,
                        clinic_id=schedule.clinic.id,
                        schedule_id=schedule.id,
                        current_step=schedule.current_step,
                        scheduled_at=schedule.scheduled_date or timezone.now(),
                    )
                    results[channel] = True
                    continue
                
                ok = self._send_through_notifier(schedule, channel)
                results[channel] = ok

            _all_successful = all(results.values())
            step_should_advance = any(
                success for channel, success in results.items() if channel in blocking_channels
            )
            
            # Grava o histórico de todas as tentativas
            with transaction.atomic():
                for schedule in schedules_in_group:
                    # Verifica o resultado específico para o canal deste agendamento.
                    success = results.get(schedule.channel, False)
                    
                    if schedule.channel not in results:
                        # Pula canais que não foram processados (ex: 'letter')
                        continue

                    # Define o status final individualmente.
                    final_status = ContactSchedule.Status.APPROVED if success else ContactSchedule.Status.REJECTED
                    
                    schedule.status = final_status
                    schedule.updated_at = timezone.now()
                    schedule.save(update_fields=["status", "updated_at"])
                    msg = self.notification_service.message_repo.get_message(
                        schedule.channel, schedule.current_step, schedule.clinic_id
                    )

                    # Registra o histórico para cada tentativa, com seu resultado real.
                    ContactHistory.objects.get_or_create(
                        schedule_id=schedule.id,
                        contact_type=schedule.channel,
                        defaults=dict(
                            patient_id=schedule.patient.id,
                            contract_id=schedule.contract.id,
                            clinic_id=schedule.clinic.id,
                            message_id=msg.id if msg else None,
                            sent_at=timezone.now(),
                            success=success,
                        ),
                    )

            if step_should_advance:
                self._advance_step(ContactScheduleEntity.from_model(representative_schedule))

            return {"patient_id": str(patient_id), "step": current_step, "results": results, "advanced_step": step_should_advance}

        except Exception:
            logger.exception("schedule_group.unhandled_error", patient_id=str(patient_id), contract_id=str(contract_id))
            return None
        
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

            for representative_schedule in self.schedule_repo.stream_pending(
                clinic_id=cmd.clinic_id,
                only_pending=cmd.only_pending,
                chunk_size=cmd.batch_size,
            ):
                result = self._process_schedule_group(representative_schedule)
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
        inst = self.notification_service.installment_repo.get_current_installment(schedule.contract)
        if not inst:
            logger.error("send_notifier.precondition_failed", reason="current_installment_not_found", schedule_id=schedule.id, contract_id=schedule.contract_id)
            return False
        patient = self.notification_service.patient_repo.find_by_id(str(schedule.patient.id))
        msg = self.message_repo.get_message(channel, schedule.current_step, schedule.clinic)
        if not (patient and msg and inst):
            logger.error("send_notifier.precondition_failed", reason="patient_msg_or_inst_missing", schedule_id=schedule.id)
            return False
        try:
            self.notification_service.send(msg, patient, inst)
            logger.info(
                "send_notifier.success",
                schedule_id=schedule.id,
                patient_id=schedule.patient.id,
                channel=channel,
                msg_type=msg.type
            )
            return True
        except PermanentNotificationError as e:
            # ERRO GRAVE E PERMANENTE: Logamos como ERRO.
            # A notificação é descartada (retorna False) e não será tentada novamente.
            # O log detalhado é a prova para compliance de que o envio falhou por um motivo válido e imutável.
            logger.error(
                "send_notifier.permanent_failure",
                reason="O destinatário ou a requisição são inválidos. A notificação não será reenviada.",
                schedule_id=schedule.id,
                patient_id=schedule.patient.id,
                channel=channel,
                error_details=str(e)
            )
            return False
            
        except TemporaryNotificationError as e:
            # ERRO TEMPORÁRIO: Logamos como AVISO.
            # A notificação falhou, mas a causa pode ser resolvida (ex: servidor voltou ao ar).
            # Por enquanto, retornamos False. No futuro, aqui entraria a lógica de retentativa.
            # O log como 'warning' ajuda a monitorar a saúde dos serviços de terceiros.
            logger.warning(
                "send_notifier.temporary_failure",
                reason="O serviço do provedor falhou ou houve um erro de rede. Pode ser tentado novamente.",
                schedule_id=schedule.id,
                patient_id=schedule.patient.id,
                channel=channel,
                error_details=str(e)
            )
            return False

        except Exception as _e:
            # ERRO INESPERADO: Logamos com 'exception' para capturar o traceback completo.
            # Essencial para debugar problemas não previstos na programação.
            logger.exception(
                "send_notifier.unhandled_error",
                reason="Uma falha inesperada ocorreu no fluxo de envio.",
                schedule_id=schedule.id,
                patient_id=schedule.patient.id,
                channel=channel,
            )
            return False