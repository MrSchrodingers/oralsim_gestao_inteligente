from datetime import date
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from oralsin_core.adapters.observability.metrics import (
    BUSINESS_AVG_OVERDUE_DAYS,
    BUSINESS_COLLECTION_RATE,
    BUSINESS_OVERDUE_PAYMENTS,
    BUSINESS_TOTAL_CONTRACTS,
    BUSINESS_TOTAL_PATIENTS,
    BUSINESS_TOTAL_RECEIVABLES,
)
from oralsin_core.core.application.dtos.dashboard_dto import (
    CollectionSummaryDTO,
    DashboardDTO,
    NotificationSummaryDTO,
    PaymentSummaryDTO,
    StatsDTO,
)
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
from oralsin_core.core.domain.services.formatter_service import FormatterService
from plugins.django_interface.models import (
    BillingSettings,
    CollectionCase,
    ContactHistory,
    ContactSchedule,
    PendingCall,
)


class DashboardService:
    def __init__(
        self,
        user_clinic_repo: UserClinicRepository,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        patient_repo: PatientRepository,
        formatter: FormatterService,
    ):
        self.user_clinic_repo = user_clinic_repo
        self.contract_repo = contract_repo
        self.installment_repo = installment_repo
        self.patient_repo = patient_repo
        self.formatter = formatter

    def _build_payment_summary(self, inst: InstallmentEntity, status: str) -> PaymentSummaryDTO:
        contract = self.contract_repo.find_by_id(inst.contract_id)
        if contract is None:
            raise ValueError(f"Contrato não encontrado para id={inst.contract_id}")
        patient = self.patient_repo.find_by_id(contract.patient_id)
        if patient is None:
            raise ValueError(f"Paciente não encontrado para id={contract.patient_id}")

        return PaymentSummaryDTO(
            id=inst.id,
            patient=patient.name,
            amount=self.formatter.format_currency(inst.installment_amount),
            date=self.formatter.format_date(inst.due_date),
            status=status,
        )

    def get_summary(self, user_id: str) -> DashboardDTO:  # noqa: PLR0912, PLR0915
        # 1) pega clínicas do usuário
        user_clinics = self.user_clinic_repo.find_by_user(user_id)
        if not user_clinics:
            empty = StatsDTO(
                totalReceivables="0",
                paidThisMonth="0",
                pendingPayments="0",
                overduePayments="0",
                collectionRate=0,
                totalContracts=0,
                totalPatients=0,
                averageDaysOverdue=0.0,
                overdueContracts=0,
            )
            return DashboardDTO(stats=empty, recentPayments=[], pendingPayments=[])

        clinic_id = user_clinics[0].clinic_id

        # 2) busca todos os contratos e calcula tot. contratos/pacientes
        contracts = self.contract_repo.list_by_clinic(clinic_id)
        total_contracts = len(contracts)
        total_patients = len({c.patient_id for c in contracts})

        # 3) coleta todas as parcelas de forma eficiente
        if not contracts:
            all_installments = []
        else:
            contract_ids = [c.id for c in contracts]
            all_installments = self.installment_repo.find_by_contract_ids(contract_ids)

        today = date.today()
        month_start = today.replace(day=1)

        total_amount = paid_amount = paid_month = pending_amount = overdue_amount = Decimal("0.0")
        paid_list: list[InstallmentEntity] = []
        pending_list: list[InstallmentEntity] = []
        days_overdue: list[int] = []
        overdue_contracts = set()

        for inst in all_installments:
            amt = inst.installment_amount
            total_amount += amt
            if inst.received:
                paid_amount += amt
                if month_start <= inst.due_date <= today:
                    paid_month += amt
                paid_list.append(inst)
            else:
                if inst.due_date < today:
                    overdue_amount += amt
                    days_overdue.append((today - inst.due_date).days)
                    overdue_contracts.add(inst.contract_id)
                else:
                    pending_amount += amt
                pending_list.append(inst)

        avg_overdue = round(sum(days_overdue) / len(days_overdue), 2) if days_overdue else 0.0
        collection_rate = int((paid_amount / total_amount) * 100) if total_amount > 0 else 0

        stats = StatsDTO(
            totalReceivables=self.formatter.format_currency(total_amount),
            paidThisMonth=self.formatter.format_currency(paid_month),
            pendingPayments=self.formatter.format_currency(pending_amount),
            overduePayments=self.formatter.format_currency(overdue_amount),
            collectionRate=collection_rate,
            totalContracts=total_contracts,
            totalPatients=total_patients,
            averageDaysOverdue=avg_overdue,
            overdueContracts=len(overdue_contracts),
        )

        label = str(clinic_id)
        BUSINESS_TOTAL_RECEIVABLES.labels(label).set(float(total_amount))
        BUSINESS_OVERDUE_PAYMENTS.labels(label).set(float(overdue_amount))
        BUSINESS_COLLECTION_RATE.labels(label).set(collection_rate)
        BUSINESS_TOTAL_CONTRACTS.labels(label).set(total_contracts)
        BUSINESS_TOTAL_PATIENTS.labels(label).set(total_patients)
        BUSINESS_AVG_OVERDUE_DAYS.labels(label).set(avg_overdue)
        
        # 4) top-3 recentes e pendentes
        recent = sorted(paid_list, key=lambda i: i.due_date, reverse=True)[:3]
        upcoming = sorted(pending_list, key=lambda i: i.due_date)[:3]

        recent_dtos = [self._build_payment_summary(i, "paid") for i in recent]
        pending_dtos = [self._build_payment_summary(i, "pending") for i in upcoming]
        
        billing_settings = int((
            BillingSettings.objects.filter(
                clinic_id=clinic_id,
            ).first()
        ).min_days_overdue)

        # 5) métricas de notificações e cobranças
        pending_scheds = (
            ContactSchedule.objects.filter(
                clinic_id=clinic_id,
                status=ContactSchedule.Status.PENDING,
                scheduled_date__lte=timezone.now(),
            ).count()
        )
        notifications_sent = ContactHistory.objects.filter(clinic_id=clinic_id).count()
        pending_calls = PendingCall.objects.filter(
            clinic_id=clinic_id, status=PendingCall.Status.PENDING
        ).count()
        step_qs = (
            ContactSchedule.objects.filter(
                clinic_id=clinic_id, status=ContactSchedule.Status.PENDING
            )
            .values("current_step")
            .annotate(total=Count("id"))
        )
        by_step = {row["current_step"]: row["total"] for row in step_qs}
        notification_summary = NotificationSummaryDTO(
            pendingSchedules=pending_scheds,
            sentNotifications=notifications_sent,
            pendingCalls=pending_calls,
            byStep=by_step,
        )

        total_cases = CollectionCase.objects.filter(clinic_id=clinic_id).count()
        with_pipe = CollectionCase.objects.filter(
            clinic_id=clinic_id, deal_id__isnull=False
        ).count()
        without_pipe = CollectionCase.objects.filter(
            clinic_id=clinic_id, deal_id__isnull=True
        ).count()

        overdue_min_days_patients: set[str] = set()
        overdue_patients: set[str] = set()
        pre_overdue_patients: set[str] = set()
        contract_map = {c.id: c.patient_id for c in contracts}
        for inst in all_installments:
            patient_id = contract_map.get(inst.contract_id)
            if not patient_id:
                continue
            if inst.received:
                continue
            if inst.due_date < today:
                overdue_patients.add(patient_id)
                if (today - inst.due_date).days >= billing_settings:
                    overdue_min_days_patients.add(patient_id)
            else:
                pre_overdue_patients.add(patient_id)

        collection_summary = CollectionSummaryDTO(
            totalCases=total_cases,
            withPipeboard=with_pipe,
            withoutPipeboard=without_pipe,
            overdueMinDaysPlus=len(overdue_min_days_patients),
            overduePatients=len(overdue_patients),
            preOverduePatients=len(pre_overdue_patients),
        )

        return DashboardDTO(
            stats=stats,
            recentPayments=recent_dtos,
            pendingPayments=pending_dtos,
            notification=notification_summary,
            collection=collection_summary,
        )
