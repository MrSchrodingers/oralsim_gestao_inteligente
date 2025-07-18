from __future__ import annotations

from collections.abc import Mapping as TMapping
from datetime import datetime, time, timedelta
from typing import Any
from uuid import UUID

import structlog
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.repositories.billing_settings_repository import (
    BillingSettingsRepository,
)
from oralsin_core.core.domain.repositories.installment_repository import (
    InstallmentRepository,
)

from notification_billing.core.domain.entities.contact_schedule_entity import (
    ContactScheduleEntity,
)
from notification_billing.core.domain.repositories.contact_schedule_repository import (
    ContactScheduleRepository,
)
from plugins.django_interface.models import (
    ContactSchedule as Schedule,
)
from plugins.django_interface.models import (
    Contract,
    FlowStepConfig,
)

log = structlog.get_logger(__name__)

# ───────────────────────────────────────────────────────────── constants
#: prioridades para agendamentos pré‑vencimento (dias antes do due_date)
_PRE_DUE_PRIORITIES: tuple[int, ...] = (7, 5, 2, 1, 0)

#: cache simples de configs ativas {step: FlowStepConfig}
_CFG_CACHE: dict[int, FlowStepConfig] = {}

# canais manuais que NÃO travam o fluxo
_MANUAL_Q = Q(channel="letter") | Q(channel="phonecall", pending_calls=True)
# ----------------------------------------------------------------------
class ContactScheduleRepoImpl(ContactScheduleRepository):
    """Repositório/serviço de agendamentos de contato."""

    def __init__(
        self,
        installment_repo: InstallmentRepository,
        billing_settings_repo: BillingSettingsRepository,
    ) -> None:
        self.installment_repo = installment_repo
        self.settings = billing_settings_repo

    # ───────────────────────────────────────────────────────── public API
    def cancel_pending_for_patient(self, patient_id: str) -> None:  # noqa: D401
        """Marca qualquer schedule pendente desse paciente como CANCELLED."""
        (
            Schedule.objects.filter(
                patient_id=patient_id, status=Schedule.Status.PENDING
            ).update(status=Schedule.Status.CANCELLED)
        )

    # ------------------------------------------------------------------
    def schedule_first_contact(
        self,
        *,
        patient_id: str,
        contract_id: str,
        clinic_id: str,
        installment_id: str | None = None,
    ) -> ContactScheduleEntity | None:  # noqa: C901
        """Cria / atualiza o primeiro agendamento automático.

        ‑ Garante **1** schedule PENDING por (patient, channel)
        ‑ Se já existir: atualiza *step*, *scheduled_date* & *installment*
        ‑ Não dispara exceção quando fora da janela `min_days_overdue` –
          apenas ignora (importante para *bulk resync*).
        """
        # 0) Clínica autorizou notificações?
        if not Contract.objects.filter(id=contract_id, do_notifications=True).exists():
            return None

        # 1) Parcela alvo
        inst = (
            self.installment_repo.find_by_id(installment_id)
            if installment_id
            else self.installment_repo.get_current_installment(contract_id)
        )
        if not inst or inst.received:
            return None

        cfgs = self._flow_configs()
        try:
            step, sched_dt = self._decide_step_and_date(
                inst=inst,
                cfg0=cfgs[0],
                min_days=self.settings.get(clinic_id).min_days_overdue,
            )
        except _SkipSchedule:
            return None

        cfg = cfgs.get(step)
        if not cfg:
            return None

        # 2) UPSERT por canal ──────────────────────────────────────────
        created: Schedule | None = None
        with transaction.atomic():
            for ch in cfg.channels:
                existing = Schedule.objects.filter(
                    patient_id=patient_id,
                    channel=ch,
                    notification_trigger=Schedule.Trigger.AUTOMATED,
                    status=Schedule.Status.PENDING,
                ).first()

                log.debug(
                    "schedule_lookup",
                    patient_id=patient_id,
                    channel=ch,
                    exists=bool(existing),
                    current_step=getattr(existing, "current_step", None),
                    install_id=getattr(existing, "installment_id", None),
                )
                obj, was_new = Schedule.objects.update_or_create(
                    patient_id=patient_id,
                    channel=ch,
                    notification_trigger=Schedule.Trigger.AUTOMATED,
                    status=Schedule.Status.PENDING,
                    defaults=dict(
                        contract_id=contract_id,
                        clinic_id=clinic_id,
                        installment_id=inst.id,
                        current_step=step,
                        scheduled_date=sched_dt,
                        advance_flow=False,
                    ),
                )
                if was_new and created is None:
                    created = obj

        if created is None:  # já existiam – pega o + recente
            created = (
                Schedule.objects.filter(
                    patient_id=patient_id,
                    channel__in=cfg.channels,
                    status=Schedule.Status.PENDING,
                )
                .order_by("-updated_at")
                .first()
            )

        return ContactScheduleEntity.from_model(created) if created else None

    # ------------------------------------------------------------------ other helpers
    def has_pending(self, patient_id: str, contract_id: str) -> bool:  # noqa: D401
        return Schedule.objects.filter(
            patient_id=patient_id,
            contract_id=contract_id,
            notification_trigger=Schedule.Trigger.AUTOMATED,
            status=Schedule.Status.PENDING,
        ).exists()

    def upsert(  # noqa: PLR0913
        self,
        *,
        patient_id: str,
        contract_id: str,
        clinic_id: str,
        installment_id: str,
        step: int,
        scheduled_dt: datetime,
    ) -> ContactScheduleEntity:
        cfg = self._flow_configs()[step]
        first: Schedule | None = None
        with transaction.atomic():
            for ch in cfg.channels:
                m, _ = Schedule.objects.update_or_create(
                    patient_id=patient_id,
                    channel=ch,
                    notification_trigger=Schedule.Trigger.AUTOMATED,
                    status=Schedule.Status.PENDING,
                    defaults=dict(
                        contract_id=contract_id,
                        clinic_id=clinic_id,
                        installment_id=installment_id,
                        current_step=step,
                        scheduled_date=scheduled_dt,
                        advance_flow=False,
                    ),
                )
                first = first or m
        return ContactScheduleEntity.from_model(first)  # type: ignore[arg-type]

    def set_status_done(self, schedule_id: str) -> ContactScheduleEntity:
        m = Schedule.objects.get(id=schedule_id)
        m.status = Schedule.Status.APPROVED
        m.save(update_fields=["status", "updated_at"])
        return ContactScheduleEntity.from_model(m)
    
    def _pending(self, clinic_id: str) -> list[ContactScheduleEntity]:
        qs = Schedule.objects.filter(
            clinic_id=clinic_id,
            scheduled_date__lte=timezone.now()
        )
        return [ContactScheduleEntity.from_model(m) for m in qs]

    def list_pending(self, clinic_id: str) -> list[ContactScheduleEntity]:
        return self._pending(clinic_id)
    
    def filter(self, **filtros) -> list[ContactScheduleEntity]:
        qs = Schedule.objects.filter(**filtros)
        return [ContactScheduleEntity.from_model(m) for m in qs]

    def get_by_patient_contract(
        self, patient_id: str, contract_id: str
    ) -> ContactScheduleEntity | None:
        m = (
            Schedule.objects
            .filter(patient_id=patient_id, contract_id=contract_id)
            .order_by("-created_at")
            .first()
        )
        return ContactScheduleEntity.from_model(m) if m else None

    def stream_pending(
        self,
        clinic_id,
        *,
        only_pending: bool = True,
        chunk_size: int = 100,
    ):
        """
        Gera lotes de ContactSchedule (Django models) com lock otimista.
        Não segura locks por longos períodos; cada lote abre/fecha transação.
        """
        base = Schedule.objects.filter(clinic_id=clinic_id)
        if only_pending:
            base = base.filter(status=Schedule.Status.PENDING)
        base = base.order_by("scheduled_date")

        while True:
            with transaction.atomic():
                batch = list(
                    base.select_for_update(skip_locked=True)[:chunk_size]
                )
            if not batch:
                break
            yield from batch
                
    def advance_contact_step(self, schedule_id: str) -> ContactScheduleEntity:
        if not self._can_advance(schedule_id):
            return
        
        with transaction.atomic():
            # 1) tranca o schedule atual
            m = Schedule.objects.select_for_update().get(id=schedule_id)
            m.status = Schedule.Status.APPROVED
            m.save(update_fields=["status", "updated_at"])

            # 2) recupera a parcela para saber o due_date
            inst = self.installment_repo.find_by_id(m.installment_id)
            if not inst:
                # se por algum motivo não achar, retorna o próprio schedule aprovado
                return ContactScheduleEntity.from_model(m)

            # 3) calcula o próximo step
            next_step = m.current_step + 1
            try:
                cfg = FlowStepConfig.objects.get(step_number=next_step, active=True)
            except FlowStepConfig.DoesNotExist:
                return ContactScheduleEntity.from_model(m)

            # 4) decide nova data de agendamento:
            today = timezone.now().date()
            if inst.due_date > today:
                # pré-vencimento: usa a lista de prioridades (7,5,2,1,0)
                days_priorities = [7, 5, 2, 1, 0]
                target = None
                for d in days_priorities:
                    cand = inst.due_date - timedelta(days=d)
                    if cand > today:
                        target = cand
                        break
                if target is None:
                    target = inst.due_date
                scheduled_dt = timezone.make_aware(datetime.combine(target, time.min))
            else:
                # pós-vencimento: reseta pelo cooldown do próprio step
                cooldown = cfg.cooldown_days or 7
                scheduled_dt = timezone.now() + timedelta(days=cooldown)

            # 5) cria os novos schedules por canal
            new_models = []
            try:
                for channel in cfg.channels:
                    new_m = Schedule.objects.create(
                        patient=m.patient,
                        contract=m.contract,
                        clinic=m.clinic,
                        installment_id=m.installment_id,
                        notification_trigger=m.notification_trigger,
                        advance_flow=False,
                        current_step=cfg.step_number,
                        channel=channel,
                        scheduled_date=scheduled_dt,
                        status=Schedule.Status.PENDING,
                    )
                    new_models.append(new_m)
            except IntegrityError:
                    log.debug("schedule already exists, skipping", schedule=m.id)

            return ContactScheduleEntity.from_model(new_models[0] if new_models else m)


    def find_by_id(self, schedule_id: str) -> ContactScheduleEntity | None:
        try:
            m = Schedule.objects.get(id=schedule_id)
            return ContactScheduleEntity.from_model(m)
        except Schedule.DoesNotExist:
            return None

    def save(self, schedule: ContactScheduleEntity) -> ContactScheduleEntity:
        m, _ = Schedule.objects.update_or_create(
            id=schedule.id,
            defaults=schedule.to_dict()
        )
        return ContactScheduleEntity.from_model(m)

    def delete(self, schedule_id: str) -> None:
        Schedule.objects.filter(id=schedule_id).delete()
    
    def find_pending_by_channel(self, clinic_id: str, channel: str) -> list[ContactScheduleEntity]:
        now = timezone.now()
        schedules = Schedule.objects.filter(
            clinic_id=clinic_id,
            channel=channel,
            status=Schedule.Status.PENDING,
            scheduled_date__lte=now
        ).order_by('scheduled_date')
        
        return [ContactScheduleEntity.from_model(s) for s in schedules]

    def _can_advance(self, schedule_id: str) -> bool:
        """
        Retorna **True** se NÃO houver pendências bloqueantes
        (sms / whatsapp / email).

        • Ignora o próprio schedule `schedule_id`, que ainda está PENDING
        quando essa verificação roda.
        • Considera apenas schedules AUTOMATIZADOS (`notification_trigger=AUTOMATED`).
        • Despreza pendências manuais (`letter` ou `phonecall` com `pending_calls=True`).
        """
        try:
            sched = Schedule.objects.get(id=schedule_id)
        except Schedule.DoesNotExist:
            # se o objeto sumiu, nada a bloquear → permite avanço
            return True

        blockers = (
            Schedule.objects.filter(
                patient_id=sched.patient_id,
                contract_id=sched.contract_id,
                status=Schedule.Status.PENDING,
                notification_trigger=Schedule.Trigger.AUTOMATED,
            )
            # descarta o próprio schedule e os pendentes MANUAIS
            .exclude(id=schedule_id)
            .exclude(_MANUAL_Q)
        )
        return not blockers.exists()

    def bulk_update_status(self, schedule_ids: list[UUID], new_status: str) -> None:
        Schedule.objects.filter(id__in=schedule_ids).update(status=new_status)

    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[Schedule]:
        """
        lista com paginação genérica.
        """
        qs = Schedule.objects.all()
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        objs_page = qs.order_by("current_step")[offset : offset + page_size]

        items = [ContactScheduleEntity.from_model(obj) for obj in objs_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)

    def get_status_summary_by_clinic(self, clinic_id: str) -> dict[str, Any]:
        """
        Calcula um sumário de agendamentos de contato para uma clínica,
        agrupando tanto por status quanto por canal de comunicação.

        Args:
            clinic_id: O ID da clínica para a qual o sumário será gerado.

        Returns:
            Um dicionário contendo agregações. Exemplo:
            {
                "PENDING": 50,
                "SENT": 250,
                "ERROR": 5,
                "by_channel": [
                    {'channel': 'whatsapp', 'count': 200},
                    {'channel': 'sms', 'count': 105}
                ]
            }
        """
        schedules_for_clinic = Schedule.objects.filter(clinic_id=clinic_id)

        # 1. Agrega por status para obter a contagem de cada um
        status_counts = schedules_for_clinic.values('status').annotate(count=Count('id'))

        # Converte a lista de dicionários em um único dicionário para fácil acesso
        summary = {item['status']: item['count'] for item in status_counts}

        # 2. Agrega por canal para a análise de canais mais usados
        channel_counts = (
            schedules_for_clinic.values('channel')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Adiciona a análise por canal ao resultado principal
        summary['by_channel'] = list(channel_counts)

        return summary
    
    @staticmethod
    def _flow_configs() -> TMapping[int, FlowStepConfig]:
        """Carrega as configurações ativas em cache (por *step*)."""
        if not _CFG_CACHE:
            _CFG_CACHE.update({cfg.step_number: cfg for cfg in FlowStepConfig.objects.filter(active=True)})
        return _CFG_CACHE

    def _decide_step_and_date(
        self,
        *,
        inst,
        cfg0: FlowStepConfig,
        min_days: int,
    ) -> tuple[int, datetime]:
        """Calcula `(step, scheduled_datetime)`.

        Levanta **_SkipSchedule** se a parcela está fora da janela.
        """
        today = timezone.localdate()

        # ─── Pré‑vencimento ───────────────────────────────────────────
        if inst.due_date > today:
            target_date = next(
                (
                    inst.due_date - timedelta(days=d)
                    for d in _PRE_DUE_PRIORITIES
                    if inst.due_date - timedelta(days=d) > today
                ),
                inst.due_date,
            )
            return 0, timezone.make_aware(datetime.combine(target_date, time.min))

        # ─── Pós‑vencimento ──────────────────────────────────────────
        days_overdue = (today - inst.due_date).days
        if days_overdue > min_days:
            raise _SkipSchedule

        raw_step = days_overdue // (cfg0.cooldown_days or 7) + 1
        step = min(raw_step, max(self._flow_configs().keys()))
        return step, timezone.now()


class _SkipSchedule(Exception):
    """Exceção interna (control‑flow) para indicar que o agendamento deve ser ignorado."""
