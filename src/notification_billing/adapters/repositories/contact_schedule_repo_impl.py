from __future__ import annotations

import itertools
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.repositories.billing_settings_repository import BillingSettingsRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository

from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity
from notification_billing.core.domain.repositories.contact_schedule_repository import ContactScheduleRepository
from plugins.django_interface.models import ContactHistory, FlowStepConfig
from plugins.django_interface.models import ContactSchedule as Schedule

log = structlog.get_logger(__name__)

class ContactScheduleRepoImpl(ContactScheduleRepository):
    """
    Repositório para persistência e consulta de agendamentos de contato (ContactSchedule).
    Esta classe é responsável exclusivamente pelo acesso a dados, sem regras de negócio complexas.
    """

    def __init__(
        self,
        installment_repo: InstallmentRepository,
        contract_repo: ContractRepository,
        billing_settings_repo: BillingSettingsRepository,
    ) -> None:
        self.installment_repo = installment_repo
        self.contract_repo = contract_repo
        self.settings = billing_settings_repo

    # ───────────────────────── MÉTODOS DE PERSISTÊNCIA ──────────────────────────

    def upsert(  # noqa: PLR0913
        self,
        *,
        patient_id: str,
        contract_id: str,
        clinic_id: str,
        installment_id: str,
        step: int,
        scheduled_dt: datetime,
    ) -> ContactScheduleEntity | None:
        """
        Cria ou atualiza os agendamentos para um determinado step do fluxo.
        Garante a idempotência criando um agendamento PENDING por canal definido no step.
        Retorna a entidade do primeiro agendamento criado/atualizado.
        """
        try:
            cfg = FlowStepConfig.objects.get(step_number=step, active=True)
            channels_for_step = cfg.channels
        except FlowStepConfig.DoesNotExist:
            log.warning("upsert.flow_step_not_found", step=step)
            return None

        first_schedule_model: Schedule | None = None
        with transaction.atomic():
            for channel in channels_for_step:
                model, _ = Schedule.objects.update_or_create(
                    patient_id=patient_id,
                    channel=channel,
                    notification_trigger=Schedule.Trigger.AUTOMATED,
                    status=Schedule.Status.PENDING,
                    defaults=dict(
                        contract_id=contract_id,
                        clinic_id=clinic_id,
                        installment_id=installment_id,
                        current_step=step,
                        scheduled_date=scheduled_dt,
                    ),
                )
                if first_schedule_model is None:
                    first_schedule_model = model
        
        return ContactScheduleEntity.from_model(first_schedule_model) if first_schedule_model else None

    def set_status_done(self, schedule_id: str) -> ContactScheduleEntity | None:
        """Marca um agendamento específico como 'APPROVED' (concluído)."""
        try:
            model = Schedule.objects.get(id=schedule_id)
            model.status = Schedule.Status.APPROVED
            model.save(update_fields=["status", "updated_at"])
            return ContactScheduleEntity.from_model(model)
        except Schedule.DoesNotExist:
            log.warning("set_status_done.not_found", schedule_id=schedule_id)
            return None

    def cancel_pending_for_patient(self, patient_id: str, except_installment_id: str | None = None) -> None:
        """Marca qualquer schedule PENDENTE de um paciente como CANCELLED."""
        query = Schedule.objects.filter(
            patient_id=patient_id, status=Schedule.Status.PENDING
        )
        if except_installment_id:
            query = query.exclude(installment_id=except_installment_id)
        query.update(status=Schedule.Status.CANCELLED, updated_at=timezone.now())

    def bulk_update_status(self, schedule_ids: list[UUID], new_status: str) -> None:
        """Atualiza o status de múltiplos agendamentos de uma só vez."""
        Schedule.objects.filter(id__in=schedule_ids).update(status=new_status)

    def delete(self, schedule_id: str) -> None:
        """Remove um agendamento do banco de dados."""
        Schedule.objects.filter(id=schedule_id).delete()

    # Método save para compatibilidade com a interface
    def save(self, schedule: ContactScheduleEntity) -> ContactScheduleEntity:
        """Salva uma entidade de agendamento no banco de dados."""
        model, _ = Schedule.objects.update_or_create(
            id=schedule.id,
            defaults=schedule.to_dict()
        )
        return ContactScheduleEntity.from_model(model)

    # ────────────────────────── MÉTODOS DE CONSULTA ───────────────────────────

    def find_by_id(self, schedule_id: str) -> ContactScheduleEntity | None:
        """Busca um agendamento pelo seu ID."""
        try:
            model = Schedule.objects.get(id=schedule_id)
            return ContactScheduleEntity.from_model(model)
        except Schedule.DoesNotExist:
            return None

    def has_schedule_for_patient(self, patient_id: str) -> bool:
        """Verifica eficientemente se já existe QUALQUER agendamento para um paciente."""
        return Schedule.objects.filter(patient_id=patient_id).exists()
    
    def has_pending_for_patient(self, patient_id: str) -> bool:
        """Verifica eficientemente se já existe QUALQUER agendamento com status PENDING para um paciente."""
        return Schedule.objects.filter(patient_id=patient_id, status=Schedule.Status.PENDING).exists()

    # Método filter para compatibilidade com a interface
    def filter(self, **filtros) -> list[ContactScheduleEntity]:
        """Filtra agendamentos com base em um dicionário de critérios."""
        qs = Schedule.objects.filter(**filtros)
        return [ContactScheduleEntity.from_model(m) for m in qs]

    # Método find_pending_by_channel para o handler de cartas
    def find_pending_by_channel(self, clinic_id: str, channel: str) -> list[ContactScheduleEntity]:
        """Encontra agendamentos pendentes para um canal e clínica específicos."""
        now = timezone.now()
        schedules = Schedule.objects.filter(
            clinic_id=clinic_id,
            channel=channel,
            status=Schedule.Status.PENDING,
            scheduled_date__lte=now
        ).order_by('scheduled_date')
        return [ContactScheduleEntity.from_model(s) for s in schedules]

    # Método get_by_patient_contract para o handler de envio manual
    def get_by_patient_contract(self, patient_id: str, contract_id: str) -> ContactScheduleEntity | None:
        """Busca o agendamento mais recente para um paciente e contrato."""
        model = Schedule.objects.filter(
            patient_id=patient_id, contract_id=contract_id
        ).order_by("-created_at").first()
        return ContactScheduleEntity.from_model(model) if model else None

    # Método has_pending para compatibilidade
    def has_pending(self, patient_id: str, contract_id: str) -> bool:
        """Verifica se existem agendamentos PENDENTES para um paciente/contrato."""
        return Schedule.objects.filter(
            patient_id=patient_id,
            contract_id=contract_id,
            status=Schedule.Status.PENDING
        ).exists()

    # Método list_pending para compatibilidade
    def list_pending(self, clinic_id: str) -> list[ContactScheduleEntity]:
        """Lista todos os agendamentos pendentes de uma clínica."""
        qs = Schedule.objects.filter(
            clinic_id=clinic_id,
            status=Schedule.Status.PENDING,
            scheduled_date__lte=timezone.now()
        )
        return [ContactScheduleEntity.from_model(m) for m in qs]
        
    # Método stream_pending para o processo em lote
    def stream_pending(
        self,
        clinic_id,
        *,
        only_pending: bool = True,
        chunk_size: int = 100,
        mode: str = "all",  # "all" | "pre_due" | "overdue"
    ):
        """
        Gera 1 representante por (paciente, contrato, step), já filtrando:
          - status pendente
          - data agendada <= agora
          - modo: pré-vencimento (step=0) ou inadimplente (step>=1 ou step==99)
        """
        base = Schedule.objects.filter(clinic_id=clinic_id)

        if only_pending:
            base = base.filter(status=Schedule.Status.PENDING)

        # Só o que está “liberado” para envio
        base = base.filter(scheduled_date__lte=timezone.now())

        if mode == "pre_due":
            base = base.filter(current_step=0)
        elif mode == "overdue":
            base = base.filter(Q(current_step__gte=1) | Q(current_step=99))

        representative_ids_query = (
            base.order_by("patient_id", "contract_id", "current_step", "scheduled_date")
               .distinct("patient_id", "contract_id", "current_step")
               .values_list('id', flat=True)
        )

        ids_iterator = representative_ids_query.iterator(chunk_size=chunk_size)
        while True:
            batch_ids = list(itertools.islice(ids_iterator, chunk_size))
            if not batch_ids:
                break
            batch_schedules = Schedule.objects.filter(id__in=batch_ids)
            yield from batch_schedules
    
    def has_history_for_patient(self, patient_id: str) -> bool:
        return ContactHistory.objects.filter(patient_id=patient_id).exists()

    def has_any_contact_for_patient(self, patient_id: str) -> bool:
        """True se já houve contato efetivo (history) OU há/agora houve schedule pendente que virou contato."""
        return (
            ContactHistory.objects.filter(patient_id=patient_id).exists()
            or Schedule.objects.filter(patient_id=patient_id).exists()
        )

    def has_only_cancelled_schedules(self, patient_id: str) -> bool:
        return Schedule.objects.filter(patient_id=patient_id).exists() and \
               not Schedule.objects.filter(patient_id=patient_id, status=Schedule.Status.PENDING).exists() and \
               not ContactHistory.objects.filter(patient_id=patient_id).exists()
               
    def list(self, filtros: dict[str, Any] | None, page: int, page_size: int) -> PagedResult[ContactScheduleEntity]:
        """Retorna uma lista paginada de agendamentos com base em filtros."""
        qs = Schedule.objects.all()
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        page_qs = qs.order_by("-scheduled_date")[offset : offset + page_size]

        items = [ContactScheduleEntity.from_model(obj) for obj in page_qs]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
    
    def get_status_summary_by_clinic(self, clinic_id: str) -> dict[str, Any]:
        """Calcula um sumário de agendamentos para uma clínica, agrupando por status e canal."""
        schedules_for_clinic = Schedule.objects.filter(clinic_id=clinic_id)
        
        status_counts = schedules_for_clinic.values('status').annotate(count=Count('id'))
        summary = {item['status']: item['count'] for item in status_counts}
        
        channel_counts = (
            schedules_for_clinic.values('channel')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        summary['by_channel'] = list(channel_counts)
        return summary