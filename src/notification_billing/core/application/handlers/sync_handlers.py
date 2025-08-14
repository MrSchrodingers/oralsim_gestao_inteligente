from django.db import transaction
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository

from notification_billing.core.application.commands.contact_commands import AdvanceContactStepCommand
from notification_billing.core.application.commands.sync_commands import BulkScheduleContactsCommand
from notification_billing.core.application.cqrs import CommandHandler
from notification_billing.core.application.services.contact_service import ContactSchedulingService
from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity
from notification_billing.core.domain.repositories.flow_step_config_repository import FlowStepConfigRepository
from notification_billing.core.domain.repositories.pending_call_repository import PendingCallRepository


class AdvanceContactStepHandler(CommandHandler[AdvanceContactStepCommand]):
    def __init__(self, scheduling: ContactSchedulingService):
        self.scheduling = scheduling

    @transaction.atomic
    def handle(self, cmd: AdvanceContactStepCommand) -> ContactScheduleEntity | None:
        return self.scheduling.advance_after_success(cmd.schedule_id)
    

class BulkScheduleContactsHandler(CommandHandler[BulkScheduleContactsCommand]):
    """
    Realiza o agendamento em massa dos contatos para pacientes inadimplentes.
    Delega a lógica de agendamento para o ContactSchedulingService, após validar
    quais contratos estão aptos a receber notificações.
    """

    def __init__(
        self,
        contract_repo: ContractRepository,
        scheduling_service: ContactSchedulingService,
        config_repo: FlowStepConfigRepository,
        pending_call_repo: PendingCallRepository,
        logger=None,
    ) -> None:
        self.contract_repo = contract_repo
        self.scheduling_service = scheduling_service
        self.config_repo = config_repo
        self.pending_call_repo = pending_call_repo
        self.logger = logger

    @transaction.atomic
    def handle(self, cmd: BulkScheduleContactsCommand) -> None:
        total_created = total_skipped = 0
        total_ignored = 0 

        contracts = self.contract_repo.list_by_clinic(cmd.clinic_id)
        self.logger.info(
            "bulk_scheduling_started",
            clinic_id=cmd.clinic_id,
            contracts_found=len(contracts),
            min_days_overdue=cmd.min_days_overdue, 
        )

        for contract in contracts:
            if not getattr(contract, "do_billing", False):
                total_ignored += 1
                continue

            sched = self.scheduling_service.schedule_initial(
                patient_id=contract.patient_id,
                contract_id=contract.id,
                clinic_id=contract.clinic_id,
            )

            if not sched:
                total_skipped += 1
                continue

            # Gera PendingCall se o step agendado exigir "phonecall"
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
                installment_id=sched.installment_id,
                step=sched.current_step,
                scheduled_date=str(sched.scheduled_date),
            )

        self.logger.info(
            "bulk_scheduling_finished",
            clinic_id=cmd.clinic_id,
            created=total_created,
            skipped_installments=total_skipped,
            ignored_contracts=total_ignored,
        )