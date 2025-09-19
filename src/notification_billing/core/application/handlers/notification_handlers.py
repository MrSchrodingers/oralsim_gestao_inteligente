import atexit
from typing import Any

import structlog
from django.db import DatabaseError, transaction
from django.utils import timezone
from oralsin_core.core.application.dtos.contact_dtos import ContactInfoDTO, ContactPhoneDTO
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.entities.patient_entity import PatientEntity
from oralsin_core.core.domain.repositories.clinic_phone_repository import ClinicPhoneRepository
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
from notification_billing.adapters.notifiers.sms.assertiva import AssertivaSMS
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
from notification_billing.core.domain.entities.message_entity import MessageEntity
from notification_billing.core.domain.events.events import NotificationSentEvent
from notification_billing.core.domain.events.exceptions import (
    MissingContactInfoError,
    NotificationError,
    PermanentNotificationError,
    TemporaryNotificationError,
)
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
    Renderiza e envia notificações. Contém a lógica central para determinar o
    destinatário correto (paciente ou pagante).
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        patient_repo: PatientRepository,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        clinic_phone_repo: ClinicPhoneRepository
    ):
        self.message_repo = message_repo
        self.patient_repo = patient_repo
        self.contract_repo = contract_repo
        self.installment_repo = installment_repo
        self.clinic_phone_repo = clinic_phone_repo
        
    # --- MUDANÇA: Lógica centralizada para obter o alvo do contato ---
    def _get_notification_target(self, inst: InstallmentEntity, patient: PatientEntity) -> ContactInfoDTO:
        """
        Única fonte de verdade para determinar os dados de contato.
        Se a parcela tem um pagador terceiro, usa seus dados.
        Caso contrário, usa os dados do paciente.
        """
        target = inst.payer

        # Se não há pagador ou o pagador É o paciente, use os dados do paciente.
        if not target or target.is_patient_the_payer:
            return ContactInfoDTO(
                name=patient.name,
                email=patient.email,
                phones=[
                    ContactPhoneDTO(phone.phone_number, phone.phone_type)
                    for phone in (patient.phones or [])
                ]
            )
        
        # Se há um pagador terceiro, use os dados dele.
        return ContactInfoDTO(
            name=target.name,
            email=target.email,
            phones=[
                ContactPhoneDTO(phone.phone_number, phone.phone_type)
                for phone in target.phones.all()
            ]
        )

    def _render_content(self, msg: MessageEntity, contact_info: ContactInfoDTO, inst: InstallmentEntity) -> str:
        overdue_count = self.installment_repo.count_overdue_by_contract(
            contract_id=inst.contract_id
        )
        # Busca o telefone da clínica pelo ID do contrato da parcela, que é mais seguro
        contract_entity = self.contract_repo.find_by_id(inst.contract_id)
        if not contract_entity:
            raise ValueError(f"Contrato com ID {inst.contract_id} não encontrado.")

        phone_entity = self.clinic_phone_repo.find_contact_by_clinic_id(contract_entity.clinic_id)
        contact_phone = ""
        if phone_entity and getattr(phone_entity, "phone_number", None):
            contact_phone = str(phone_entity.phone_number).strip()
        
        ctx = {
            "nome": contact_info.name, 
            "valor": f"R$ {inst.installment_amount:.2f}",
            "vencimento": inst.due_date.strftime("%d/%m/%Y"),
            "total_parcelas_em_atraso": overdue_count,
            "contact_phone": contact_phone
        }
        return render_message(msg.content, ctx)
    
    def _channels_for_step(self, schedule: ContactSchedule) -> list[str]:
        cfg = FlowStepConfig.objects.get(step_number=schedule.current_step)
        return [c for c in cfg.channels if c not in ("letter", "pending_call")]

    def _pick_phone(self, contact_info: ContactInfoDTO) -> str:
        """
        Escolhe o melhor telefone do alvo do contato (paciente ou pagante).
        """
        if not contact_info.phones:
            raise MissingContactInfoError(f"O contato '{contact_info.name}' não possui telefones cadastrados.")

        mobiles = [p.phone_number for p in contact_info.phones if p.phone_type == "mobile" and p.phone_number]
        if mobiles:
            return mobiles[0]

        for phone in contact_info.phones:
            if phone.phone_number:
                return phone.phone_number

        raise MissingContactInfoError(f"O contato '{contact_info.name}' não possui número de telefone utilizável.")
    
    def send(self, msg: MessageEntity, patient: PatientEntity, inst: InstallmentEntity) -> None:
        # 1. Determina o alvo correto da notificação
        contact_info = self._get_notification_target(inst, patient)
        
        # 2. Renderiza o conteúdo com os dados do alvo
        content = self._render_content(msg, contact_info, inst)
        notifier = get_notifier(msg.type)

        try:
            if msg.type == "email":
                if not contact_info.email:
                    raise MissingContactInfoError(f"Destinatário '{contact_info.name}' não possui e-mail.")
                notifier.send(
                    recipients=[contact_info.email],
                    subject="Notificação de Atraso de Parcelas.",
                    html=content,
                )
            elif msg.type in ("sms", "whatsapp"):
                phone_number = self._pick_phone(contact_info)
                if msg.type == "sms":
                    notifier.send(phones=[phone_number], message=content)
                else:  # whatsapp
                    dto = WhatsappNotificationDTO(to=str(phone_number), message=content)
                    notifier.send(dto)
            else:
                raise NotImplementedError(f"Canal não suportado: {msg.type}")
        except HTTPError as http_err:
            status_code = http_err.response.status_code
            if 400 <= status_code < 500:
                raise PermanentNotificationError(f"Erro permanente do cliente (HTTP {status_code}): {http_err}") from http_err
            elif 500 <= status_code < 600:
                raise TemporaryNotificationError(f"Erro temporário no servidor (HTTP {status_code}): {http_err}") from http_err
            else:
                raise TemporaryNotificationError(f"Erro HTTP inesperado: {http_err}") from http_err
        
        except Exception as e:
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

    @publish(exchange="notifications", routing_key="manual")
    def handle(self, cmd: SendManualNotificationCommand) -> dict[str, Any]:
        try:
            sched = self.schedule_repo.get_by_patient_contract(
                cmd.patient_id, cmd.contract_id
            )
            contract = self.contract_repo.find_by_id(sched.contract_id)
            if not contract or not contract.do_notifications:
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

            if cmd.channel == "phonecall":
                self.pending_call_repo.create(
                    patient_id=sched.patient_id,
                    contract_id=sched.contract_id,
                    clinic_id=sched.clinic_id,
                    schedule_id=sched.id,
                    current_step=sched.current_step,
                    scheduled_at=sched.scheduled_date or timezone.now(),
                )
                sent_hist = None
            else:
                msg = self.notification_service.message_repo.get_message(
                    cmd.channel, sched.current_step, sched.clinic_id
                )
                patient = self.notification_service.patient_repo.find_by_id(
                    str(sched.patient_id)
                )
                # A chamada ao `send` não muda, pois a lógica está encapsulada nele.
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
            _success = False
            raise


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

    # ... (os métodos _process_schedule, _handle_phonecall, etc. que você tem podem ser mantidos)
    # A mudança principal está no método que efetivamente envia a notificação.
    
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

            step_should_advance = any(
                success for channel, success in results.items() if channel in blocking_channels
            )
            
            with transaction.atomic():
                for schedule in schedules_in_group:
                    success = results.get(schedule.channel, False)
                    if schedule.channel not in results:
                        continue

                    final_status = ContactSchedule.Status.APPROVED if success else ContactSchedule.Status.REJECTED
                    schedule.status = final_status
                    schedule.updated_at = timezone.now()
                    schedule.save(update_fields=["status", "updated_at"])
                    msg = self.notification_service.message_repo.get_message(
                        schedule.channel, schedule.current_step, schedule.clinic_id
                    )
                    observation = "automated send" if success else f"error sending via {schedule.channel}"
                    self.history_repo.save_from_schedule(
                        schedule=schedule,
                        sent_at=timezone.now(),
                        success=success,
                        channel=schedule.channel,
                        observation=observation,
                        message=msg
                    )

            if step_should_advance:
                self._advance_step(ContactScheduleEntity.from_model(representative_schedule))

            return {"patient_id": str(patient_id), "step": current_step, "results": results, "advanced_step": step_should_advance}

        except Exception:
            logger.exception("schedule_group.unhandled_error", patient_id=str(patient_id), contract_id=str(contract_id))
            return None
        
    def _advance_step(self, sched: ContactScheduleEntity):
        """Avança para a próxima etapa do fluxo."""
        self.command_bus.dispatch(
            AdvanceContactStepCommand(schedule_id=str(sched.id))
        )

    @publish(exchange="notifications", routing_key="automated")
    def handle(self, cmd: RunAutomatedNotificationsCommand) -> dict[str, Any]:
        processed = 0
        results: list[dict[str, Any]] = []

        for representative_schedule in self.schedule_repo.stream_pending(
            clinic_id=cmd.clinic_id,
            only_pending=cmd.only_pending,
            chunk_size=cmd.batch_size,
            mode=cmd.mode, 
        ):
            result = self._process_schedule_group(representative_schedule)
            if result is not None:
                results.append(result)
            processed += 1
        
        payload = {"clinic_id": cmd.clinic_id, "processed": processed, "results": results}
        try:
            total, sample = AssertivaSMS.flush_offline_buffer("[SMS OFFLINE][RUN]")
            logger.info("sms.offline_flush_forced", total=total, sample_path=sample)
        except Exception:
            logger.exception("sms.offline_flush_failed")
        
        return payload if processed > 0 else {"clinic_id": cmd.clinic_id, "processed": 0, "results": []}

    def _send_through_notifier(self, schedule: ContactSchedule, channel: str) -> bool:
        """
        Valida e envia a notificação, tratando a ausência de contatos do alvo correto.
        """
        inst = self.notification_service.installment_repo.get_current_installment(schedule.contract)
        if not inst:
            logger.error("send_notifier.precondition_failed", reason="current_installment_not_found", schedule_id=schedule.id)
            return False
        
        patient = self.notification_service.patient_repo.find_by_id(str(schedule.patient.id))
        msg = self.message_repo.get_message(channel, schedule.current_step, schedule.clinic)
        
        if not (patient and msg):
            logger.error("send_notifier.precondition_failed", reason="patient_or_msg_missing", schedule_id=schedule.id)
            return False

        try:
            self.notification_service.send(msg, patient, inst)
            logger.info("send_notifier.success", schedule_id=schedule.id, channel=channel)
            return True
        
        except (PermanentNotificationError, MissingContactInfoError) as e:
            logger.error(
                "send_notifier.permanent_failure",
                reason="Dados de contato inválidos ou ausentes para o destinatário.",
                schedule_id=schedule.id, channel=channel, error_details=str(e)
            )
            return False
            
        except TemporaryNotificationError as e:
            logger.warning(
                "send_notifier.temporary_failure",
                reason="Serviço do provedor falhou. Pode ser tentado novamente.",
                schedule_id=schedule.id, channel=channel, error_details=str(e)
            )
            return False

        except Exception:
            logger.exception(
                "send_notifier.unhandled_error",
                reason="Falha inesperada no fluxo de envio.",
                schedule_id=schedule.id, channel=channel
            )
            return False
        
def _flush_sms_offline_on_exit():
    try:
        AssertivaSMS.flush_offline_buffer("[SMS OFFLINE][EXIT]")
    except Exception:
        logger.exception("sms.offline_exit_flush_failed")

atexit.register(_flush_sms_offline_on_exit)