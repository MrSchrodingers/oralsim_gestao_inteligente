from oralsin_core.core.application.dtos.dashboard_dto import DashboardDTO
from oralsin_core.core.application.queries.dashboard_queries import GetDashboardSummaryQuery
from oralsin_core.core.application.services.dashboard_service import DashboardService
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
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
            user_clinic_repo, contract_repo, installment_repo, patient_repo, formatter
        )

    def handle(self, query: GetDashboardSummaryQuery) -> DashboardDTO:
        return self.service.get_summary(query.user_id)
