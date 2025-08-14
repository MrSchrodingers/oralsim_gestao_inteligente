from cordial_billing.core.domain.repositories.collection_case_repository import CollectionCaseRepository
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from notification_billing.core.domain.repositories.contact_schedule_repository import ContactScheduleRepository
from oralsin_core.core.application.dtos.dashboard_dto import DashboardDTO
from oralsin_core.core.application.queries.dashboard_queries import GetDashboardReportQuery, GetDashboardSummaryQuery
from oralsin_core.core.application.services.dashboard_pdf_service import DashboardPDFService
from oralsin_core.core.application.services.dashboard_service import DashboardService
from oralsin_core.core.domain.repositories.clinic_data_repository import ClinicDataRepository
from oralsin_core.core.domain.repositories.clinic_phone_repository import ClinicPhoneRepository
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
from oralsin_core.core.domain.repositories.user_repository import UserRepository
from oralsin_core.core.domain.services.formatter_service import FormatterService


class GetDashboardSummaryHandler:
    def __init__(
        self,
        user_clinic_repo: UserClinicRepository,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        patient_repo: PatientRepository,
        formatter: FormatterService,
    ):
        self.service = DashboardService(
            user_clinic_repo,
            contract_repo,
            installment_repo,
            patient_repo,
            formatter,
        )

    def handle(self, query: GetDashboardSummaryQuery) -> DashboardDTO:
        filtros = query.filtros or {}

        return self.service.get_summary(
            user_id=query.user_id,
            start_date=filtros.get("start_date"),
            end_date=filtros.get("end_date"),
        )

class GetDashboardReportHandler:
    """
    Handler orquestrador que coleta dados financeiros e operacionais
    de múltiplos serviços/repositórios para construir o relatório em PDF.
    """
    def __init__(  # noqa: PLR0913
        self,
        dashboard_service: DashboardService,
        pdf_service: DashboardPDFService,
        user_repo: UserRepository,
        user_clinic_repo: UserClinicRepository,
        clinic_repo: ClinicRepository,
        clinic_data_repo: ClinicDataRepository,
        clinic_phone_repo: ClinicPhoneRepository,
        collection_case_repo: CollectionCaseRepository,
        contact_history_repo: ContactHistoryRepository,
        contact_schedule_repo: ContactScheduleRepository,
    ):
        self._svc = dashboard_service
        self._pdf = pdf_service
        self._users = user_repo
        self._user_clinic_repo = user_clinic_repo
        self._clinic_repo = clinic_repo
        self._clinic_data_repo = clinic_data_repo
        self._clinic_phone_repo = clinic_phone_repo
        self._collection_case_repo = collection_case_repo
        self._contact_history_repo = contact_history_repo
        self._contact_schedule_repo = contact_schedule_repo

    def __call__(self, q: GetDashboardReportQuery) -> bytes:
        # 1. Obter dados do usuário e clínica
        user = self._users.find_by_id(q.user_id)
        user_clinic = self._user_clinic_repo.find_by_user(user.id)[0]
        clinic = self._clinic_repo.find_by_id(user_clinic.clinic_id)
        clinic_data = self._clinic_data_repo.find_by_id(user_clinic.clinic_id)
        clinic_phones = self._clinic_phone_repo.list_by_clinic(clinic.id)[0]
        
        # 2. Obter o sumário financeiro principal
        financial_summary = self._svc.get_summary(
            user_id=q.user_id,
            start_date=q.filtros.get("start_date"),
            end_date=q.filtros.get("end_date"),
        )
        
        # 3. --- COLETAR DADOS OPERACIONAIS ADICIONAIS ---
        collection_summary = self._collection_case_repo.get_summary_by_clinic(clinic.id)
        notification_summary = self._contact_schedule_repo.get_status_summary_by_clinic(clinic.id)
        last_notifications = self._contact_history_repo.get_latest_by_clinic(clinic.id, limit=5)

        # 4. Construir o PDF com todos os dados coletados
        return self._pdf.build(
            user=user,
            clinic=clinic,
            clinic_data=clinic_data,
            clinic_phones=clinic_phones,
            dashboard=financial_summary,
            collection_summary=collection_summary,
            notification_summary=notification_summary,
            last_notifications=last_notifications,
        )

    handle = __call__
