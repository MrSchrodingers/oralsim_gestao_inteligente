from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from oralsin_core.core.domain.repositories.billing_settings_repository import BillingSettingsRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository

from notification_billing.core.domain.entities.contact_schedule_entity import (
    ContactScheduleEntity,
)
from notification_billing.core.domain.events.events import NotificationScheduledEvent
from notification_billing.core.domain.repositories import (
    ContactScheduleRepository,
    FlowStepConfigRepository,
)
from notification_billing.core.domain.services.event_dispatcher import EventDispatcher


class ContactSchedulingService:
    """Regras de negócio para (re)agendar contatos de forma robusta e idempotente."""

    def __init__(  # noqa: PLR0913
        self,
        schedule_repo: ContactScheduleRepository,
        installment_repo: InstallmentRepository,
        contract_repo: ContractRepository,
        flow_cfg_repo: FlowStepConfigRepository,
        billing_settings_repo: BillingSettingsRepository,
        dispatcher: EventDispatcher,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.installment_repo = installment_repo
        self.contract_repo = contract_repo
        self.flow_cfg_repo = flow_cfg_repo
        self.billing_settings_repo = billing_settings_repo
        self.dispatcher = dispatcher

    # ─────────────────────────  API pública  ────────────────────────── #

    def schedule_initial(self, patient_id: str, contract_id: str, clinic_id: str) -> ContactScheduleEntity | None:
        """
        Agenda o contato para a parcela *is_current*.
        - Força o step 1 para o primeiro contato (mensagem amigável).
        - Calcula o step proporcional se o fluxo já foi iniciado.
        """
        inst = self.installment_repo.get_current_installment(contract_id)
        if not inst or inst.received:
            return None

        # Se não houver nenhum agendamento anterior para este paciente, é o primeiro contato.
        is_first_contact = not self.schedule_repo.has_schedule_for_patient(patient_id)

        if is_first_contact:
            # Regra de negócio: primeiro contato é sempre no step 1.
            step = 1
            when = timezone.now()
        else:
            # Já existe um agendamento pendente para este paciente?
            if self.schedule_repo.has_pending_for_patient(patient_id):
                # Se sim, não faz nada. O fluxo já está ativo e não deve ser interrompido.
                return None 

            # Se não há pendentes, aí sim calcula o step proporcional para (re)iniciar o fluxo.
            step, when = self._calculate_proportional_step_and_date(inst)

        return self._upsert_schedule(
            patient_id=patient_id,
            contract_id=contract_id,
            clinic_id=clinic_id,
            installment_id=inst.id,
            step=step,
            scheduled_dt=when,
        )

    def advance_after_success(self, schedule_id: str) -> ContactScheduleEntity | None:
        """
        Marca o agendamento como concluído e avança para o step proporcional ao atraso.
        Implementa a transição para o fluxo de "Cordial Billing" (> 90 dias).
        """
        with transaction.atomic():
            current = self.schedule_repo.set_status_done(schedule_id)
            billing_settings = self.billing_settings_repo.get(current.clinic_id)
            min_days_overdue = billing_settings.min_days_overdue or 90


            if not current:
                return None

            inst = self.installment_repo.find_by_id(current.installment_id)
            if not inst or inst.received:
                return current # Encerra se a parcela foi paga.

            # Verifica a regra de transição para o Cordial Billing
            days_overdue = (timezone.localdate() - inst.due_date).days
            if days_overdue > min_days_overdue:
                contract = self.contract_repo.find_by_id(current.contract_id)
                if contract and not contract.do_billings:
                    # Altera a flag do contrato e encerra o fluxo de notificação
                    contract.do_billings = True
                    self.contract_repo.update(contract)
                    return current  # Retorna o schedule concluído, sem agendar um próximo.

            # Calcula o próximo step com base no atraso real.
            next_step, next_when = self._calculate_proportional_step_and_date(inst)

            # Garante que não vamos repetir o mesmo step. Se o cálculo resultar no mesmo step, avança para o próximo.
            if next_step <= current.current_step:
                next_step = current.current_step + 1

            next_cfg = self.flow_cfg_repo.find_by_step(next_step)
            if not next_cfg:  # Fluxo de notificação chegou ao fim.
                return current

            next_sched = self._upsert_schedule(
                patient_id=current.patient_id,
                contract_id=current.contract_id,
                clinic_id=current.clinic_id,
                installment_id=current.installment_id,
                step=next_cfg.step_number,
                scheduled_dt=next_when,
            )
            return next_sched

    # ─────────────────────────  Helpers  ────────────────────────── #

    def _calculate_proportional_step_and_date(self, inst):
        """Calcula o step e a data do agendamento com base no vencimento da parcela."""
        today = timezone.localdate()
        
        # Assume-se que o cooldown é padrão (7 dias) para o cálculo do step.
        # A configuração específica do step só é usada para o *próximo* agendamento.
        cooldown_period = 7 

        if inst.due_date > today:  # Pré-vencimento
            step = 0 # Step 0 é para lembretes amigáveis pré-vencimento.
            target_date = inst.due_date - timedelta(days=cooldown_period)
            when = timezone.make_aware(datetime.combine(target_date, time.min))
        else:  # Pós-vencimento
            days_overdue = (today - inst.due_date).days
            # +1 para alinhar com os steps (semana 1, 2, etc.)
            raw_step = (days_overdue // cooldown_period) + 1
            max_step = self.flow_cfg_repo.max_active_step()
            step = min(raw_step, max_step)
            when = timezone.now()

        return step, when

    def _upsert_schedule(  # noqa: PLR0913
        self,
        *,
        patient_id: str,
        contract_id: str,
        clinic_id: str,
        installment_id: str,
        step: int,
        scheduled_dt: datetime,
    ) -> ContactScheduleEntity:
        """
        **Idempotente**: Garante UM único schedule `PENDING` por paciente,
        cancelando agendamentos pendentes anteriores antes de criar/atualizar.
        """
        with transaction.atomic():
            self.schedule_repo.cancel_pending_for_patient(patient_id, except_installment_id=installment_id)
            sched = self.schedule_repo.upsert(
                patient_id=patient_id,
                contract_id=contract_id,
                clinic_id=clinic_id,
                installment_id=installment_id,
                step=step,
                scheduled_dt=scheduled_dt,
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
        return sched