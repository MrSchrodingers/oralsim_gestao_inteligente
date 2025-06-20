from datetime import datetime, time, timedelta
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.repositories.billing_settings_repository import BillingSettingsRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository

from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity
from notification_billing.core.domain.repositories.contact_schedule_repository import ContactScheduleRepository
from plugins.django_interface.models import ContactSchedule as ContactScheduleModel
from plugins.django_interface.models import Contract as ContractModel
from plugins.django_interface.models import FlowStepConfig


class ContactScheduleRepoImpl(ContactScheduleRepository):
    def __init__(self, installment_repo: InstallmentRepository, billing_settings_repo: BillingSettingsRepository):
        self.installment_repo = installment_repo
        self.billing_settings_repo = billing_settings_repo

    def cancel_pending_for_patient(self, patient_id: str) -> None:
        (ContactScheduleModel.objects
            .filter(patient_id=patient_id, status=ContactScheduleModel.Status.PENDING)
            .update(status=ContactScheduleModel.Status.CANCELLED))
        
    def schedule_first_contact(  # noqa: PLR0911, PLR0912
        self,
        patient_id: str,
        contract_id: str,
        clinic_id: str,
        installment_id: str | None = None,
    ) -> ContactScheduleEntity | None:
        """
        - Se vier installment_id: agendar exatamente essa parcela (via find_by_id).
        - Se NÃO vier installment_id: pegar o GET_CURRENT_INSTALLMENT (via is_current).
        """
        # 0) Valida permissão para agendar/ notificar paciente
        if not ContractModel.objects.filter(id=contract_id, do_notifications=True).exists():
            return None
        settings = self.billing_settings_repo.get(clinic_id)
        min_days = settings.min_days_overdue

        # 1) buscar a parcela certa
        inst = self.installment_repo.find_by_id(installment_id) if installment_id else self.installment_repo.get_current_installment(contract_id)

        # se não achou ou já recebeu, sai sem agendar
        if not inst or inst.received:
            return None

        today = timezone.now().date()

        # 2) carregar todos os steps ativos (0…14)
        configs = {
            cfg.step_number: cfg
            for cfg in FlowStepConfig.objects.filter(active=True)
        }
        cfg0 = configs.get(0)
        if not cfg0:
            return None

        # 3) decidir se é pré-vencimento (step=0) ou vencida (step≥1)
        if inst.due_date > today:
            # ─────────── pré-vencimento ───────────
            # Agendar 7, 5, 2, 1 ou 0 dias antes do vencimento, na ordem de prioridade
            step = 0
            days_priorities = [7, 5, 2, 1, 0]
            target = None
            for d in days_priorities:
                candidate = inst.due_date - timedelta(days=d)
                if candidate > today:
                    target = candidate
                    break
            # se todos os candidatos já passaram, agenda no dia do vencimento
            if target is None:
                target = inst.due_date
            scheduled_dt = timezone.make_aware(datetime.combine(target, time.min))

        else:
            # ─────────── vencida ───────────
            days_overdue = (today - inst.due_date).days
            if days_overdue > min_days:
                return None
            
            cooldown = cfg0.cooldown_days or 7
            raw_step = days_overdue // cooldown + 1
            max_step = max(configs.keys())
            step = min(raw_step, max_step)
            scheduled_dt = timezone.now()

        cfg = configs.get(step)
        if not cfg:
            return None

         # 3.1) se já existe um agendamento PENDING para este mesmo step+canal, não criar de novo
        existing = ContactScheduleModel.objects.filter(
            patient_id=patient_id,
            contract_id=contract_id,
            current_step=step,
            notification_trigger=ContactScheduleModel.Trigger.AUTOMATED,
            status=ContactScheduleModel.Status.PENDING,
        )
        if existing.exists():
            return None

        # 4) upsert um registro por canal
        created = None
        with transaction.atomic():
            for channel in cfg.channels:
                m, was_new = ContactScheduleModel.objects.update_or_create(
                    patient_id=patient_id,
                    contract_id=contract_id,
                    current_step=step,
                    channel=channel,
                    notification_trigger=ContactScheduleModel.Trigger.AUTOMATED,
                    defaults={
                        "clinic_id":      clinic_id,
                        "installment_id": inst.id,
                        "advance_flow":   False,
                        "scheduled_date": scheduled_dt,
                        "status":         ContactScheduleModel.Status.PENDING,
                    },
                )
                if was_new and created is None:
                    created = m

        # se já existia um schedule igual, pega o mais recente atualizado
        if not created:
            created = (
                ContactScheduleModel.objects
                .filter(
                    patient_id=patient_id,
                    contract_id=contract_id,
                    current_step=step,
                    notification_trigger=ContactScheduleModel.Trigger.AUTOMATED
                )
                .order_by("-updated_at")
                .first()
            )

        return ContactScheduleEntity.from_model(created) if created else None

    def has_pending(self, patient_id: str, contract_id: str) -> bool:
        return ContactScheduleModel.objects.filter(
            patient_id=patient_id,
            contract_id=contract_id,
            notification_trigger=ContactScheduleModel.Trigger.AUTOMATED,
            status=ContactScheduleModel.Status.PENDING,
        ).exists()
    
    def upsert(self, *, patient_id, contract_id, clinic_id, # noqa
               installment_id, step, scheduled_dt):
        channel_set = FlowStepConfig.objects.get(step_number=step).channels
        objs = []
        for ch in channel_set:
            obj, _ = ContactScheduleModel.objects.update_or_create(
                patient_id=patient_id,
                contract_id=contract_id,
                current_step=step,
                channel=ch,
                notification_trigger=ContactScheduleModel.Trigger.AUTOMATED,
                defaults=dict(
                    clinic_id=clinic_id,
                    installment_id=installment_id,
                    scheduled_date=scheduled_dt,
                    status=ContactScheduleModel.Status.PENDING,
                ),
            )
            objs.append(obj)
        return ContactScheduleEntity.from_model(objs[0])

    def set_status_done(self, schedule_id: str) -> ContactScheduleEntity:
        m = ContactScheduleModel.objects.get(id=schedule_id)
        m.status = ContactScheduleModel.Status.APPROVED
        m.save(update_fields=["status", "updated_at"])
        return ContactScheduleEntity.from_model(m)
    
    def _pending(self, clinic_id: str) -> list[ContactScheduleEntity]:
        qs = ContactScheduleModel.objects.filter(
            clinic_id=clinic_id,
            scheduled_date__lte=datetime.utcnow()
        )
        return [ContactScheduleEntity.from_model(m) for m in qs]

    def list_pending(self, clinic_id: str) -> list[ContactScheduleEntity]:
        return self._pending(clinic_id)
    
    def filter(self, **filtros) -> list[ContactScheduleEntity]:
        qs = ContactScheduleModel.objects.filter(**filtros)
        return [ContactScheduleEntity.from_model(m) for m in qs]

    def get_by_patient_contract(
        self, patient_id: str, contract_id: str
    ) -> ContactScheduleEntity | None:
        m = (
            ContactScheduleModel.objects
            .filter(patient_id=patient_id, contract_id=contract_id)
            .order_by("-created_at")
            .first()
        )
        return ContactScheduleEntity.from_model(m) if m else None

    def advance_contact_step(self, schedule_id: str) -> ContactScheduleEntity:
        with transaction.atomic():
            # 1) tranca o schedule atual
            m = ContactScheduleModel.objects.select_for_update().get(id=schedule_id)
            m.status = ContactScheduleModel.Status.APPROVED
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
            for channel in cfg.channels:
                new_m = ContactScheduleModel.objects.create(
                    patient=m.patient,
                    contract=m.contract,
                    clinic=m.clinic,
                    installment_id=m.installment_id,
                    notification_trigger=m.notification_trigger,
                    advance_flow=False,
                    current_step=cfg.step_number,
                    channel=channel,
                    scheduled_date=scheduled_dt,
                    status=ContactScheduleModel.Status.PENDING,
                )
                new_models.append(new_m)

            return ContactScheduleEntity.from_model(new_models[0] if new_models else m)


    def find_by_id(self, schedule_id: str) -> ContactScheduleEntity | None:
        try:
            m = ContactScheduleModel.objects.get(id=schedule_id)
            return ContactScheduleEntity.from_model(m)
        except ContactScheduleModel.DoesNotExist:
            return None

    def save(self, schedule: ContactScheduleEntity) -> ContactScheduleEntity:
        m, _ = ContactScheduleModel.objects.update_or_create(
            id=schedule.id,
            defaults=schedule.to_dict()
        )
        return ContactScheduleEntity.from_model(m)

    def delete(self, schedule_id: str) -> None:
        ContactScheduleModel.objects.filter(id=schedule_id).delete()
    
    def find_pending_by_channel(self, clinic_id: str, channel: str) -> list[ContactScheduleEntity]:
        now = timezone.now()
        schedules = ContactScheduleModel.objects.filter(
            clinic_id=clinic_id,
            channel=channel,
            status=ContactScheduleModel.Status.PENDING,
            scheduled_date__lte=now
        ).order_by('scheduled_date')
        
        return [ContactScheduleEntity.from_model(s) for s in schedules]

    def bulk_update_status(self, schedule_ids: list[UUID], new_status: str) -> None:
        ContactScheduleModel.objects.filter(id__in=schedule_ids).update(status=new_status)

    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[ContactScheduleModel]:
        """
        lista com paginação genérica.
        """
        qs = ContactScheduleModel.objects.all()
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
        schedules_for_clinic = ContactScheduleModel.objects.filter(clinic_id=clinic_id)

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
    