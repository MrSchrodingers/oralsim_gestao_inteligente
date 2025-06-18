import io

from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository

# Imports de notification_billing
from notification_billing.core.application.cqrs import PagedResult, QueryHandler
from notification_billing.core.application.dtos.letter_dto import LetterListItemDTO
from notification_billing.core.application.queries.letter_queries import GetLetterPreviewQuery, ListLettersQuery
from notification_billing.core.application.services.letter_context_builder import LetterContextBuilder
from notification_billing.core.application.services.letter_service import CordialLetterService

# Imports de oralsin_core
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from notification_billing.core.domain.repositories.contact_schedule_repository import ContactScheduleRepository
from notification_billing.core.domain.repositories.flow_step_config_repository import FlowStepConfigRepository
from plugins.django_interface.models import ContactSchedule


class ListLettersHandler(QueryHandler[ListLettersQuery, PagedResult[LetterListItemDTO]]):
    """Handler para listar cartas enviadas e agendadas de forma precisa e paginada."""

    def __init__(
        self,
        history_repo: ContactHistoryRepository,
        schedule_repo: ContactScheduleRepository,
        patient_repo: PatientRepository,
        contract_repo: ContractRepository,
        config_repo: FlowStepConfigRepository,
    ):
        self.history_repo = history_repo
        self.schedule_repo = schedule_repo
        self.patient_repo = patient_repo
        self.contract_repo = contract_repo
        self.config_repo = config_repo

    def handle(self, query: ListLettersQuery) -> PagedResult[LetterListItemDTO]:
        all_items = []
        filtros = query.filtros
        
        # 1. Coleta das cartas já enviadas, agora aplicando os filtros recebidos.
        history_filtros = {"channel": "letter", **filtros}
        sent_letters = self.history_repo.filter(**history_filtros)
        if sent_letters:
            for hist in sent_letters:
                patient = self.patient_repo.find_by_id(hist.patient_id)
                contract = self.contract_repo.find_by_id(hist.contract_id)
                all_items.append(LetterListItemDTO(
                    id=hist.id,
                    patient_name=patient.name if patient else "Paciente não encontrado",
                    contract_id=contract.oralsin_contract_id if contract else "Contrato não encontrado",
                    status="Enviada",
                    relevant_date=hist.sent_at,
                    item_type="history",
                ))

        # 2. Coleta das cartas agendadas
        all_configs = self.config_repo.all()
        letter_steps = {
            config.step_number 
            for config in all_configs
            if "letter" in config.channels and config.active
        }
        
        if letter_steps:
            schedule_filtros = {"status": ContactSchedule.Status.PENDING, **filtros}
            pending_schedules = self.schedule_repo.filter(**schedule_filtros)
            if pending_schedules:
                for sched in pending_schedules:
                    if sched.current_step in letter_steps:
                        patient = self.patient_repo.find_by_id(sched.patient_id)
                        contract = self.contract_repo.find_by_id(sched.contract_id)
                        all_items.append(LetterListItemDTO(
                            id=sched.id,
                            patient_name=patient.name if patient else "Paciente não encontrado",
                            contract_id=contract.oralsin_contract_id if contract else "Contrato não encontrado",
                            status="Agendada",
                            relevant_date=sched.scheduled_date,
                            item_type="schedule",
                        ))
            
        # 3. Ordena e Pagina (lógica existente)
        sorted_items = sorted(all_items, key=lambda item: item.relevant_date, reverse=True)

        total = len(sorted_items)
        page = query.page
        page_size = query.page_size
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        paginated_items = sorted_items[start_index:end_index]
        
        return PagedResult(
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size
        )


class GetLetterPreviewHandler(QueryHandler[GetLetterPreviewQuery, io.BytesIO]):
    """Handler para gerar o documento .docx de uma carta específica."""

    def __init__(self, *, context_builder: LetterContextBuilder, letter_service: CordialLetterService, **kwargs):
        self.history_repo: ContactHistoryRepository = kwargs.get("history_repo")
        self.schedule_repo: ContactScheduleRepository = kwargs.get("schedule_repo")
        self.context_builder: LetterContextBuilder = context_builder
        self.letter_service: CordialLetterService  = letter_service

    def handle(self, query: GetLetterPreviewQuery) -> io.BytesIO:
        item = ( self.history_repo.find_by_id(query.item_id) if query.item_type == "history"
                 else self.schedule_repo.find_by_id(query.item_id) )
        if not item:
            raise FileNotFoundError("Item não encontrado.")

        context = self.context_builder.build(
            patient_id  = item.patient_id,
            contract_id = item.contract_id,
            clinic_id   = item.clinic_id,
            installment_id = getattr(item, "installment_id", None),
        )
        return self.letter_service.generate_letter(context)