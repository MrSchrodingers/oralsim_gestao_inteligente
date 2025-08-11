from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from oralsin_core.core.application.dtos.clinic_summary_dto import ClinicSummaryDTO
from oralsin_core.core.application.dtos.dashboard_dto import (
    AmicableSummaryDTO,
    DashboardDTO,
    MonthlyReceivableDTO,
    NotificationActivityDTO,
    NotificationSummaryDTO,
    PaymentSummaryDTO,
    ReceivablesSummaryDTO,
    StatsDTO,
)
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
from oralsin_core.core.domain.services.formatter_service import FormatterService
from plugins.django_interface.models import (
    BillingSettings,
    ClinicData,  # ROI opcional
    CollectionCase,
    ContactHistory,
    ContactSchedule,
    PendingCall,
)
from plugins.django_interface.models import Installment as InstallmentORM


class DashboardService:
    def __init__(  # noqa: PLR0913
        self,
        user_clinic_repo: UserClinicRepository,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        patient_repo: PatientRepository,
        formatter: FormatterService,
        clinic_repo: ClinicRepository | None = None,
    ):
        self.user_clinic_repo = user_clinic_repo
        self.contract_repo = contract_repo
        self.installment_repo = installment_repo
        self.patient_repo = patient_repo
        self.formatter = formatter
        self.clinic_repo = clinic_repo

    # ▶ pagamentos (evita N+1 usando cache simples de pacientes/contratos)
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

    # ▶ notificação
    def _build_notification_activity(self, h: ContactHistory) -> NotificationActivityDTO:
        patient = self.patient_repo.find_by_id(h.patient_id)
        patient_name = patient.name if patient else "Paciente desconhecido"
        return NotificationActivityDTO(
            id=str(h.id),
            channel=h.contact_type,
            patient=patient_name,
            sent_at=self.formatter.format_date(h.sent_at),
            success=h.success,
        )

    # ▶ agregador mensal (últimos 12 meses)
    def _build_monthly_receivables(
        self, installments: list[InstallmentEntity], months: int = 12
    ) -> list[MonthlyReceivableDTO]:
        today = date.today().replace(day=1)                  # primeiro dia do mês atual
        first_month = (today - timedelta(days=months * 30)).replace(day=1)

        buckets: dict[date, dict[str, Decimal]] = defaultdict(
            lambda: {"paid": Decimal("0"), "receivable": Decimal("0")}
        )

        for inst in installments:
            if inst.due_date < first_month:
                continue
            month_key = inst.due_date.replace(day=1)
            buckets[month_key]["receivable"] += inst.installment_amount
            if inst.received:
                buckets[month_key]["paid"] += inst.installment_amount

        out: list[MonthlyReceivableDTO] = []
        for month_date in sorted(buckets):
            iso_month = month_date.strftime("%Y-%m")         # "2025-06"
            data = buckets[month_date]
            out.append(
                MonthlyReceivableDTO(
                    month=iso_month,
                    paid=float(data["paid"]),
                    receivable=float(data["receivable"]),
                )
            )
        return out or None

    def get_summary(  # noqa: PLR0912, PLR0915
        self,
        user_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> DashboardDTO:
        # 1) clínicas do usuário
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

        # 1.1) intervalo por due_date
        try:
            start_date_dt = date.fromisoformat(start_date) if start_date else None
            end_date_dt = date.fromisoformat(end_date) if end_date else None
        except ValueError as e:
            raise ValueError("start_date/end_date inválidos (YYYY-MM-DD)") from e

        # Filtros reutilizáveis
        inst_date_q = Q()  # para InstallmentORM
        if start_date_dt:
            inst_date_q &= Q(due_date__gte=start_date_dt)
        if end_date_dt:
            inst_date_q &= Q(due_date__lte=end_date_dt)

        case_date_q = Q()  # para CollectionCase (via parcela)
        if start_date_dt:
            case_date_q &= Q(installment__due_date__gte=start_date_dt)
        if end_date_dt:
            case_date_q &= Q(installment__due_date__lte=end_date_dt)

        # 2) contratos/pacientes
        contracts = self.contract_repo.list_by_clinic(clinic_id)
        total_contracts = len(contracts)
        unique_patient_ids = {c.patient_id for c in contracts}
        total_patients = len(unique_patient_ids)

        # cache nomes de paciente por contrato (evita N+1)
        patient_cache: dict[str, str] = {}
        for pid in unique_patient_ids:
            p = self.patient_repo.find_by_id(pid)
            if p:
                patient_cache[pid] = p.name
        patient_name_by_contract_id = {
            c.id: patient_cache.get(c.patient_id, "Paciente desconhecido") for c in contracts
        }

        # 3) parcelas (via repositório de domínio)
        contract_ids = [c.id for c in contracts] if contracts else []
        all_installments = self.installment_repo.find_by_contract_ids(contract_ids) if contract_ids else []

        # filtra janela
        if start_date_dt or end_date_dt:
            def in_window(inst: InstallmentEntity) -> bool:
                return ((start_date_dt is None or inst.due_date >= start_date_dt) and
                        (end_date_dt is None or inst.due_date <= end_date_dt))
            installments_window = [i for i in all_installments if in_window(i)]
        else:
            installments_window = all_installments

        today = date.today()
        month_start = today.replace(day=1)

        total_amount = Decimal("0.0")
        paid_amount = Decimal("0.0")
        paid_month = Decimal("0.0")
        pending_amount = Decimal("0.0")
        overdue_amount = Decimal("0.0")
        paid_list: list[InstallmentEntity] = []
        pending_list: list[InstallmentEntity] = []
        days_overdue: list[int] = []
        overdue_contracts = set()

        receivables_total_count = 0

        for inst in installments_window:
            amt = inst.installment_amount
            total_amount += amt
            if inst.received:
                paid_amount += amt
                # NOTE: mais fiel seria paid_at; usamos due_date por ausência no domínio
                if month_start <= inst.due_date <= today:
                    paid_month += amt
                paid_list.append(inst)
            else:
                receivables_total_count += 1
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

        # 4) recentes/pendentes (sem re-hit ao repo)
        def make_payment_summary(inst: InstallmentEntity, status: str) -> PaymentSummaryDTO:
            patient_name = patient_name_by_contract_id.get(inst.contract_id, "Paciente desconhecido")
            return PaymentSummaryDTO(
                id=inst.id,
                patient=patient_name,
                amount=self.formatter.format_currency(inst.installment_amount),
                date=self.formatter.format_date(inst.due_date),
                status=status,
            )

        recent = sorted(paid_list, key=lambda i: i.due_date, reverse=True)[:3]
        future_pending = [i for i in pending_list if i.due_date >= today]
        upcoming = sorted(future_pending, key=lambda i: i.due_date)[:3]
        recent_dtos = [make_payment_summary(i, "paid") for i in recent]
        pending_dtos = [make_payment_summary(i, "pending") for i in upcoming]

        # 5) notificações e ligações
        cfg = BillingSettings.objects.filter(clinic_id=clinic_id).first()
        min_days_overdue = int(cfg.min_days_overdue if cfg else 90)

        pending_scheds = ContactSchedule.objects.filter(
            clinic_id=clinic_id,
            status=ContactSchedule.Status.PENDING,
            scheduled_date__lte=timezone.now(),
        ).count()
        notifications_sent = ContactHistory.objects.filter(clinic_id=clinic_id).count()
        pending_calls = PendingCall.objects.filter(
            clinic_id=clinic_id, status=PendingCall.Status.PENDING
        ).count()

        step_qs = (
            ContactSchedule.objects
            .filter(clinic_id=clinic_id, status=ContactSchedule.Status.PENDING)
            .values("current_step")
            .annotate(
                total=Count("patient_id", filter=Q(status=ContactSchedule.Status.PENDING), distinct=True)
            )
        )
        by_step = {row["current_step"]: row["total"] for row in step_qs}
        notification_summary = NotificationSummaryDTO(
            pendingSchedules=pending_scheds,
            sentNotifications=notifications_sent,
            pendingCalls=pending_calls,
            byStep=by_step,
        )

        # 5.1) Conjuntos em memória (pacientes vencidos / pré-vencidos / limiar)
        overdue_min_days_patients: set[str] = set()
        overdue_patients: set[str] = set()
        pre_overdue_patients: set[str] = set()
        contract_map = {c.id: c.patient_id for c in contracts}

        for inst in installments_window:
            patient_id = contract_map.get(inst.contract_id)
            if not patient_id or inst.received:
                continue
            if inst.due_date < today:
                overdue_patients.add(patient_id)
                if (today - inst.due_date).days >= min_days_overdue:
                    overdue_min_days_patients.add(patient_id)
            else:
                pre_overdue_patients.add(patient_id)

        vencidos_set = overdue_patients
        pre_vencidos_set = pre_overdue_patients - vencidos_set
        em_cobranca_set = overdue_min_days_patients
        todos_pacientes_com_parcelas_pendentes = vencidos_set | pre_vencidos_set
        todos_pacientes_da_clinica = {c.patient_id for c in contracts}
        sem_cobranca_set = todos_pacientes_da_clinica - todos_pacientes_com_parcelas_pendentes

        # 6) KPIs corretos (negócio)
        # 6.1) Amigável (CA) — contratos com do_billings=True
        total_cases = CollectionCase.objects.filter(clinic_id=clinic_id).count()
        with_pipe = CollectionCase.objects.filter(clinic_id=clinic_id, deal_id__isnull=False).count()
        without_pipe = total_cases - with_pipe

        # Recebíveis com Debt (CollectionCase aberto) do total de recebíveis
        receivables_with_debt = (
            CollectionCase.objects
            .filter(
                clinic_id=clinic_id,
                status=CollectionCase.Status.OPEN,
                installment__received=False,
            )
            .filter(case_date_q)
            .values("installment").distinct().count()
        )

        # Vencidos em Amigável = parcelas atrasadas de contratos CA
        overdue_in_amicable = (
            InstallmentORM.objects
            .filter(
                contract__clinic_id=clinic_id,
                contract__do_billings=True,
                received=False,
                due_date__lt=today,
            )
            .filter(inst_date_q)
            .count()
        )

        # Recuperados CA = parcelas pagas em contratos CA
        recovered_ca_qs = (
            InstallmentORM.objects
            .filter(
                contract__clinic_id=clinic_id,
                contract__do_billings=True,   # CA
                received=True,
            )
            .filter(inst_date_q)
        )
                # 🔧 contagem por CONTRATO
        recovered_ca_count = (
            recovered_ca_qs
            .values("contract_id")
            .distinct()
            .count()
        )

        # 💰 soma por PARCELA (financeiro faz sentido somar tudo)
        recovered_ca_amount = (
            recovered_ca_qs.aggregate(total=Sum("installment_amount"))["total"]
            or Decimal("0.0")
        )

        amicable_summary = AmicableSummaryDTO(
            totalCases=total_cases,
            withPipeboard=with_pipe,
            withoutPipeboard=without_pipe,
            overdueMinDaysPlus=len(em_cobranca_set),
            overdueInAmicable=overdue_in_amicable,
            receivablesWithDebt=receivables_with_debt,
            recoveredCA=int(recovered_ca_count),
            recoveredCAAmount=float(recovered_ca_amount),
        )

        # 6.2) Gestão de Recebíveis (GR) — contratos com do_notifications=True
        # Total de parcelas a receber (pendentes + vencidas) — já calculado em memória:
        # receivables_total_count

        # Recuperados GR = contratos distintos com ao menos uma parcela recebida em GR
        recovered_gr_qs = (
            InstallmentORM.objects
            .filter(
                contract__clinic_id=clinic_id,
                contract__do_notifications=True,  # GR
                received=True,
            )
            .filter(inst_date_q)
        )

        # 🔧 contagem por CONTRATO
        recovered_gr_count = (
            recovered_gr_qs
            .values("contract_id")
            .distinct()
            .count()
        )

        # 💰 soma por PARCELA
        recovered_gr_amount = (
            recovered_gr_qs.aggregate(total=Sum("installment_amount"))["total"]
            or Decimal("0.0")
        )

        receivables_summary = ReceivablesSummaryDTO(
            receivablesTotalCount=receivables_total_count,
            overduePatients=len(vencidos_set),
            preOverduePatients=len(pre_vencidos_set),
            noBilling=len(sem_cobranca_set),
            recoveredGR=int(recovered_gr_count),
            recoveredGRAmount=float(recovered_gr_amount),
        )

        # 6.3) ROI (opcional; NÃO depende de BillingSettings)
        # Evita dupla contagem: ROI usa união de IDs pagos em CA e GR
        ca_ids = set(recovered_ca_qs.values_list("id", flat=True))
        gr_ids = set(recovered_gr_qs.values_list("id", flat=True))
        recovered_ids_union = list(ca_ids | gr_ids)
        recovered_total_amount = Decimal("0.0")
        if recovered_ids_union:
            recovered_total_amount = (
                InstallmentORM.objects
                .filter(id__in=recovered_ids_union)
                .aggregate(total=Sum("installment_amount"))["total"] or Decimal("0.0")
            )

        roi_pct: float | None = None
        clinic_meta = ClinicData.objects.filter(clinic_id=clinic_id).first()
        operational_cost = getattr(clinic_meta, "operational_cost_monthly", None)
        if operational_cost and operational_cost > 0:
            roi_pct = float(((recovered_total_amount - operational_cost) / operational_cost) * 100)

        # 7) monthly receivables
        monthly_dtos = self._build_monthly_receivables(all_installments)

        # 8) últimas notificações
        hist_qs = ContactHistory.objects.filter(clinic_id=clinic_id).order_by("-sent_at")[:5]
        last_notifs = [self._build_notification_activity(h) for h in hist_qs]

        return DashboardDTO(
            stats=stats,
            recentPayments=recent_dtos,
            pendingPayments=pending_dtos,
            notification=notification_summary,
            amicable=amicable_summary,          # resumo de cobrança amigável (CA)
            receivables=receivables_summary,    # resumo de gestão de recebíveis (GR)
            monthlyReceivables=monthly_dtos,
            lastNotifications=last_notifs or None,
            roi=round(roi_pct, 2) if roi_pct is not None else None,
        )

    def get_clinic_summary(
        self,
        clinic_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> "ClinicSummaryDTO":
        """Resumo simplificado para uma clínica específica."""
        try:
            start_date_dt = date.fromisoformat(start_date) if start_date else None
            end_date_dt = date.fromisoformat(end_date) if end_date else None
        except ValueError as e:
            raise ValueError("start_date/end_date inválidos (YYYY-MM-DD)") from e

        contracts = self.contract_repo.list_by_clinic(clinic_id)
        total_patients = len({c.patient_id for c in contracts})
        active_patients = len({c.patient_id for c in contracts if c.status == "ativo"})

        if contracts:
            contract_ids = [c.id for c in contracts]
            installments = self.installment_repo.find_by_contract_ids(contract_ids)
        else:
            installments = []

        if start_date_dt or end_date_dt:
            def in_window(inst: InstallmentEntity) -> bool:
                return ((start_date_dt is None or inst.due_date >= start_date_dt) and
                        (end_date_dt is None or inst.due_date <= end_date_dt))
            installments = [i for i in installments if in_window(i)]

        paid_month = Decimal("0.0")
        receivables = ContactSchedule.objects.filter(
            clinic_id=clinic_id,
            status=ContactSchedule.Status.PENDING,
        ).values("patient_id").distinct().count()

        collection_cases = CollectionCase.objects.filter(clinic_id=clinic_id).count()
        clinic = self.clinic_repo.find_by_id(clinic_id) if self.clinic_repo else None
        name = clinic.name if clinic else str(clinic_id)

        return ClinicSummaryDTO(
            id=str(clinic_id),
            name=name,
            total_patients=total_patients,
            active_patients=active_patients,
            receivables=receivables,
            collection_cases=collection_cases,
            monthly_revenue=self.formatter.format_currency(paid_month),
        )
