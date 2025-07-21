from __future__ import annotations

import itertools
from collections.abc import Mapping as TMapping
from datetime import datetime, time, timedelta
from typing import Any
from uuid import UUID

import structlog
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.repositories.billing_settings_repository import (
    BillingSettingsRepository,
)
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
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
    ContactHistory,
    ContactSchedule,
    Contract,
    FlowStepConfig,
    Installment,
)
from plugins.django_interface.models import (
    ContactSchedule as Schedule,
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
        contract_repo: ContractRepository,
        billing_settings_repo: BillingSettingsRepository,
    ) -> None:
        self.installment_repo = installment_repo
        self.contract_repo = contract_repo
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
        # 0) Clínica autorizou e contrato existe?
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

        is_new_patient_for_notifications = not ContactHistory.objects.filter(
            patient_id=patient_id
        ).exists()
        
        cfgs = self._flow_configs()
        try:
            step, sched_dt = self._decide_step_and_date(
                inst=inst,
                cfg0=cfgs[0],
                min_days=self.settings.get(clinic_id).min_days_overdue,
                is_new_patient=is_new_patient_for_notifications,
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
    def _is_step_complete(self, schedule: Schedule) -> bool:
        """
        Verifica se uma etapa do fluxo pode ser considerada concluída.

        A regra é: todos os outros agendamentos para o mesmo contrato e mesma etapa
        que são de canais bloqueantes (não são 'letter' ou 'phonecall') devem
        ter um status final ('approved', 'failed', 'cancelled').
        """
        blocking_channels = ['sms', 'whatsapp', 'email'] # Defina os canais bloqueantes
        
        # Conta quantos outros agendamentos bloqueantes para esta etapa ainda estão pendentes
        pending_blocking_schedules = Schedule.objects.filter(
            contract_id=schedule.contract_id,
            current_step=schedule.current_step,
            channel__in=blocking_channels,
            status=Schedule.Status.PENDING
        ).exclude(id=schedule.id).count()

        # Se não houver nenhum outro agendamento bloqueante pendente, a etapa está completa.
        return pending_blocking_schedules == 0
    
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
        Gera um representante de cada grupo de trabalho (paciente, contrato, etapa)
        que precisa ser processado.
        """
        base = ContactSchedule.objects.filter(clinic_id=clinic_id)
        if only_pending:
            base = base.filter(status=ContactSchedule.Status.PENDING)
            
        representative_ids_query = base.order_by(
            "patient_id", "contract_id", "current_step", "scheduled_date"
        ).distinct(
            "patient_id", "contract_id", "current_step"
        ).values_list('id', flat=True)

        # Usamos iterator() para eficiência de memória ao buscar os IDs
        ids_iterator = representative_ids_query.iterator(chunk_size=chunk_size)

        # Agrupa os IDs em lotes (batches)
        while True:
            batch_ids = list(itertools.islice(ids_iterator, chunk_size))
            if not batch_ids:
                break
            
            # Apenas busca os objetos, SEM LOCK. O lock será feito no Handler.
            batch_schedules = ContactSchedule.objects.filter(id__in=batch_ids)
            yield from batch_schedules
                
    @transaction.atomic
    def advance_contact_step(self, schedule_id: str) -> ContactScheduleEntity | None:  # noqa: PLR0911, PLR0912
        """
        Avança a etapa do fluxo para um ContactSchedule, garantindo atomicidade e idempotência.

        1.  Verifica se o avanço é permitido (não há outros agendamentos bloqueantes).
        2.  Encerra o agendamento atual (status 'APPROVED') e todos os outros pendentes
            para o mesmo contrato (status 'CANCELLED'), garantindo um único fluxo ativo.
        3.  Calcula a próxima etapa e a data do novo agendamento.
        4.  Cria os novos agendamentos para os canais da próxima etapa.
        5.  Retorna a primeira entidade do novo agendamento criado.
        """
        if not self._can_advance(schedule_id):
            log.warning("advance_step.blocked", schedule_id=schedule_id, reason="Existing pending schedules")
            return None

        # Bloqueia a linha do agendamento atual para evitar race conditions
        try:
            current_schedule = Schedule.objects.select_for_update().get(id=schedule_id)
        except Schedule.DoesNotExist:
            log.warning("advance_step.not_found", schedule_id=schedule_id)
            return None

        if current_schedule.current_step == 0:
            try:
                installment = current_schedule.installment
                is_overdue = installment.due_date < timezone.now().date()
            except Installment.DoesNotExist:
                is_overdue = False

            if not is_overdue:
                # Marca os agendamentos atuais do step 0 como concluídos
                Schedule.objects.filter(
                    contract_id=current_schedule.contract_id,
                    current_step=0,
                    status__in=[Schedule.Status.PENDING, Schedule.Status.PROCESSING]
                ).update(status=Schedule.Status.APPROVED, updated_at=timezone.now())

                # Calcula a data do próximo aviso
                next_warning_date = timezone.now() + timedelta(days=7)

                # Reagenda um novo aviso de step 0 apenas se ele ocorrer antes do vencimento
                if next_warning_date.date() < installment.due_date:
                    log.info(
                        "advance_step.rescheduling_step_0",
                        contract_id=current_schedule.contract_id,
                        next_date=next_warning_date.date()
                    )
                    cfg0 = self._flow_configs().get(0)
                    if cfg0:
                        for ch in cfg0.channels:
                            Schedule.objects.update_or_create(
                                patient_id=current_schedule.patient_id,
                                contract_id=current_schedule.contract_id,
                                current_step=0, # Continua no step 0
                                channel=ch,
                                notification_trigger=Schedule.Trigger.AUTOMATED,
                                status=Schedule.Status.PENDING,
                                defaults=dict(
                                    clinic_id=current_schedule.clinic_id,
                                    installment_id=current_schedule.installment_id,
                                    scheduled_date=next_warning_date,
                                    advance_flow=False,
                                ),
                            )
                else:
                    log.info(
                        "advance_step.stopped_at_step_0",
                        contract_id=current_schedule.contract_id,
                        reason="Due date is too close for another warning."
                    )
                
                # Interrompe o avanço para o step 1
                return None
            
            # Se chegamos aqui, é step 0 mas a parcela já venceu, então o fluxo continua para o step 1.
            log.info(
                "advance_step.advancing_from_step_0",
                contract_id=current_schedule.contract_id,
                reason="Installment is now overdue."
            )
    
        # Cancela outros agendamentos pendentes para o mesmo contrato, exceto o atual
        Schedule.objects.filter(
            contract_id=current_schedule.contract_id,
            status=Schedule.Status.PENDING
        ).exclude(id=schedule_id).update(status='cancelled', updated_at=timezone.now())

        # Marca o agendamento atual como concluído
        current_schedule.status = Schedule.Status.APPROVED
        current_schedule.save(update_fields=["status", "updated_at"])

        # Verifica se a etapa está pronta para avançar
        if not self._is_step_complete(current_schedule):
            log.info(
                "advance_step.step_not_complete",
                schedule_id=schedule_id,
                contract_id=current_schedule.contract_id,
                step=current_schedule.current_step
            )
            return None # Não avança o fluxo ainda, pois faltam outros canais.

        log.info(
            "advance_step.step_complete",
            contract_id=current_schedule.contract_id,
            step=current_schedule.current_step,
            reason="All blocking channels are done. Advancing flow."
        )

        # Se a etapa estiver completa, cancelamos os canais não-bloqueantes pendentes.
        # Isso evita que 'letter' e 'phonecall' fiquem "órfãos" no sistema.
        Schedule.objects.filter(
            contract_id=current_schedule.contract_id,
            current_step=current_schedule.current_step,
            status=Schedule.Status.PENDING,
            channel__in=['letter', 'phonecall'] # Canais não-bloqueantes
        ).update(status='cancelled', updated_at=timezone.now())
        
        # Lógica para calcular a próxima etapa e data
        next_step_number = current_schedule.current_step + 1
        try:
            next_config = FlowStepConfig.objects.get(step_number=next_step_number, active=True)
        except FlowStepConfig.DoesNotExist:
            log.info("advance_step.end_of_flow", contract_id=current_schedule.contract_id)
            return None  # Fim do fluxo

        # Calcula a data do próximo agendamento
        cooldown = next_config.cooldown_days or 7
        next_scheduled_date = timezone.now() + timedelta(days=cooldown)

        # Cria os novos agendamentos para a próxima etapa
        new_schedules = []
        for channel in next_config.channels:
            obj, created = Schedule.objects.update_or_create(
                patient_id=current_schedule.patient_id,
                contract_id=current_schedule.contract_id,
                installment_id=current_schedule.installment_id,
                current_step=next_config.step_number,
                channel=channel,
                notification_trigger=current_schedule.notification_trigger,
                status=Schedule.Status.PENDING,
                clinic_id=current_schedule.clinic_id,
                defaults={
                    'scheduled_date': next_scheduled_date,
                    'advance_flow': False,
                }
            )
            if created:
                new_schedules.append(obj)

        if not new_schedules:
            log.warning("advance_step.no_new_schedules_created", contract_id=current_schedule.contract_id)
            return None

        return ContactScheduleEntity.from_model(new_schedules[0])


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
        inst: InstallmentEntity,
        cfg0: FlowStepConfig,
        min_days: int,
        is_new_patient: bool,
    ) -> tuple[int, datetime]:
        """
        Calcula `(step, scheduled_datetime)`.

        Levanta **_SkipSchedule** se a parcela está fora da janela.
        Para novos pacientes, sempre inicia no Step 1 se a parcela estiver vencida.
        """
        today = timezone.localdate()
        patient_id = self.contract_repo.find_by_id(inst.contract_id).patient_id
        # --- Pré‑vencimento ---
        if inst.due_date > today:
            target_date = next(
                (
                    inst.due_date - timedelta(days=d)
                    for d in _PRE_DUE_PRIORITIES
                    if inst.due_date - timedelta(days=d) > today
                ),
                inst.due_date,
            )
            # Para pré-vencimento, sempre será Step 0
            return 0, timezone.make_aware(datetime.combine(target_date, time.min))

        # --- Pós‑vencimento ---
        days_overdue = (today - inst.due_date).days
        if days_overdue < 0 or days_overdue > min_days:
            raise _SkipSchedule

        # Se for um paciente novo no fluxo, ele DEVE começar no Step 1.
        if is_new_patient:
            log.info(
                "new_patient_flow.forcing_step_1",
                patient_id=patient_id,
                days_overdue=days_overdue,
            )
            return 1, timezone.now()

        # Lógica original para pacientes que já estão no fluxo
        raw_step = days_overdue // (cfg0.cooldown_days or 7) + 1
        step = min(raw_step, max(self._flow_configs().keys()))
        return step, timezone.now()


class _SkipSchedule(Exception):
    """Exceção interna (control‑flow) para indicar que o agendamento deve ser ignorado."""
