from django.db import transaction
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository

from notification_billing.core.application.commands.contact_commands import AdvanceContactStepCommand
from notification_billing.core.application.commands.sync_commands import BulkScheduleContactsCommand
from notification_billing.core.application.cqrs import CommandHandler
from notification_billing.core.application.services.contact_service import ContactSchedulingService
from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity
from notification_billing.core.domain.events.events import NotificationScheduledEvent
from notification_billing.core.domain.repositories import (
    ContactScheduleRepository,
)
from notification_billing.core.domain.repositories.flow_step_config_repository import FlowStepConfigRepository
from notification_billing.core.domain.repositories.pending_call_repository import PendingCallRepository
from notification_billing.core.domain.services.event_dispatcher import EventDispatcher


class AdvanceContactStepHandler(CommandHandler[AdvanceContactStepCommand]):
    def __init__(self, scheduling: ContactSchedulingService):
        self.scheduling = scheduling

    @transaction.atomic
    def handle(self, cmd: AdvanceContactStepCommand) -> ContactScheduleEntity:
        return self.scheduling.advance_after_success(cmd.schedule_id)
    
class BulkScheduleContactsHandler(CommandHandler[BulkScheduleContactsCommand]):
    """
    Realiza o agendamento em massa dos contatos para pacientes inadimplentes.
    Percorre todos os contratos da clínica e agenda para cada parcela vencida.
    Também gera `PendingCall` quando o step inclui o canal ``phonecall``.
    """

    def __init__(  # noqa: PLR0913
        self,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        schedule_repo: ContactScheduleRepository,
        config_repo: FlowStepConfigRepository,
        pending_call_repo: PendingCallRepository,
        dispatcher: EventDispatcher,
        logger=None,
    ) -> None:
        self.contract_repo = contract_repo
        self.installment_repo = installment_repo
        self.schedule_repo = schedule_repo
        self.config_repo = config_repo
        self.pending_call_repo = pending_call_repo
        self.dispatcher = dispatcher
        self.logger = logger

    @transaction.atomic
    def handle(self, cmd: BulkScheduleContactsCommand) -> None:  # noqa: C901
        total_created = total_skipped = 0

        contracts = self.contract_repo.list_by_clinic(cmd.clinic_id)
        self.logger.info(
            "bulk_scheduling_started",
            clinic_id=cmd.clinic_id,
            contracts=len(contracts),
            min_days_overdue=cmd.min_days_overdue,
        )

        for contract in contracts:
            # 1️⃣ parcela atual
            inst = self.installment_repo.get_current_installment(contract.id)
            if not inst or inst.received:
                continue

            # 2️⃣ já existe agendamento pendente? pula
            if self.schedule_repo.has_pending(contract.patient_id, contract.id):
                total_skipped += 1
                self.logger.debug(
                    "schedule_already_exists",
                    patient_id=contract.patient_id,
                    contract_id=contract.id,
                )
                continue

            # 3️⃣ cria agendamento inicial
            sched: ContactScheduleEntity | None = (
                self.schedule_repo.schedule_first_contact(
                    patient_id=contract.patient_id,
                    contract_id=contract.id,
                    clinic_id=contract.clinic_id,
                    installment_id=inst.id,
                )
            )
            if not sched:
                total_skipped += 1
                continue

            # 4️⃣ gera PendingCall se o step 1 exigir "phonecall"
            cfg = self.config_repo.find_by_step(sched.current_step)
            if cfg and "phonecall" in cfg.channels:
                self.pending_call_repo.create(
                    patient_id=sched.patient_id,
                    contract_id=sched.contract_id,
                    clinic_id=sched.clinic_id,
                    schedule_id=sched.id,
                    current_step=sched.current_step,
                    scheduled_at=sched.scheduled_date,
                )

            total_created += 1
            self.logger.debug(
                "schedule_created",
                patient_id=sched.patient_id,
                contract_id=sched.contract_id,
                installment_id=inst.id,
                step=sched.current_step,
                scheduled_date=str(sched.scheduled_date),
            )

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

        self.logger.info(
            "bulk_scheduling_finished",
            clinic_id=cmd.clinic_id,
            created=total_created,
            skipped=total_skipped,
        )