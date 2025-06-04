from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
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
    """Regras de negócio para (re)agendar contatos."""

    def __init__(
        self,
        schedule_repo: ContactScheduleRepository,
        installment_repo: InstallmentRepository,
        flow_cfg_repo: FlowStepConfigRepository,
        dispatcher: EventDispatcher,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.installment_repo = installment_repo
        self.flow_cfg_repo = flow_cfg_repo
        self.dispatcher = dispatcher

    # ─────────────────────────  API pública  ────────────────────────── #

    def schedule_initial(self, patient_id: str, contract_id: str, clinic_id: str) -> ContactScheduleEntity | None:
        """Agenda o primeiro contato para a parcela *is_current*."""
        inst = self.installment_repo.get_current_installment(contract_id)
        if not inst or inst.received:
            return None
        step, when = self._compute_step_and_date(inst)

        return self._upsert_schedule(
            patient_id=patient_id,
            contract_id=contract_id,
            clinic_id=clinic_id,
            installment_id=inst.id,
            step=step,
            scheduled_dt=when,
        )

    def advance_after_success(self, schedule_id: str) -> ContactScheduleEntity:
        """Marca o agendamento atual como concluído e gera o próximo passo."""
        with transaction.atomic():
            current = self.schedule_repo.set_status_done(schedule_id)

            next_cfg = self.flow_cfg_repo.get_active(current.current_step + 1)
            if not next_cfg:      # fluxo acabou
                return current

            next_when = timezone.now() + timedelta(days=next_cfg.cooldown_days)
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

    def _compute_step_and_date(self, inst):
        today = timezone.localdate()
        cfg0 = self.flow_cfg_repo.get_active(0)
        cooldown = cfg0.cooldown_days or 7

        if inst.due_date > today:            # pré-vencimento
            step = 0
            target = inst.due_date - timedelta(days=cooldown)
            when = timezone.make_aware(datetime.combine(target, time.min))
        else:                                # pós-vencimento
            days_overdue = (today - inst.due_date).days
            raw_step = (days_overdue // cooldown) + 1
            max_step = self.flow_cfg_repo.max_active_step()
            step = min(raw_step, max_step)
            when = timezone.now()

        return step, when

    def _upsert_schedule( # noqa
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
        **Idempotente**: mantém somente UM schedule `PENDING`
        por patient+contract. Caso já exista no mesmo step,
        reaproveita; caso step diferente, substitui.
        """
        with transaction.atomic():
            # Cancela/Pendura outros agendamentos ativos do paciente
            self.schedule_repo.cancel_pending_for_patient(patient_id)

            sched = self.schedule_repo.upsert(
                patient_id=patient_id,
                contract_id=contract_id,
                clinic_id=clinic_id,
                installment_id=installment_id,
                step=step,
                scheduled_dt=scheduled_dt,
            )

        # notificação de domínio
        self.dispatcher.dispatch(
            NotificationScheduledEvent(
                schedule_id=sched.id,
                patient_id=patient_id,
                contract_id=contract_id,
                step=sched.current_step,
                channel=sched.channel,
                scheduled_date=sched.scheduled_date,
            )
        )
        return sched
