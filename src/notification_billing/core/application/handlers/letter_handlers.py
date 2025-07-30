import base64
import io

import structlog
from django.utils import timezone
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository

from notification_billing.adapters.notifiers.email.microsoft_graph import MicrosoftGraphEmail
from notification_billing.adapters.notifiers.letter.letter_notifier import LetterNotifier
from notification_billing.core.application.commands.letter_commands import SendPendingLettersCommand

# Imports de notification_billing
from notification_billing.core.application.cqrs import CommandBus, CommandHandler, PagedResult, QueryHandler
from notification_billing.core.application.dtos.letter_dto import LetterListItemDTO
from notification_billing.core.application.queries.letter_queries import GetLetterPreviewQuery, ListLettersQuery
from notification_billing.core.application.services.letter_context_builder import LetterContextBuilder
from notification_billing.core.application.services.letter_service import CordialLetterService

# Imports de oralsin_core
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from notification_billing.core.domain.repositories.contact_schedule_repository import ContactScheduleRepository
from notification_billing.core.domain.repositories.flow_step_config_repository import FlowStepConfigRepository
from plugins.django_interface.models import ContactSchedule

BATCH_LETTER_RECIPIENT = "mrschrodingers@gmail.com" 
BATCH_SIZE = 50

logger = structlog.get_logger(__name__)

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
    
    
class SendPendingLettersHandler(CommandHandler[SendPendingLettersCommand]):
    def __init__(  # noqa: PLR0913
        self,
        schedule_repo: ContactScheduleRepository,
        history_repo: ContactHistoryRepository,
        clinic_repo: ClinicRepository,
        context_builder: LetterContextBuilder,
        letter_notifier: LetterNotifier,
        command_bus: CommandBus,
    ):
        self.schedule_repo = schedule_repo
        self.history_repo = history_repo
        self.clinic_repo = clinic_repo
        self.context_builder = context_builder
        self.letter_notifier = letter_notifier
        self.email_sender: MicrosoftGraphEmail = letter_notifier.email_notifier
        self.command_bus = command_bus

    def handle(self, command: SendPendingLettersCommand) -> None:
        logger.info("letter_batch.started", clinic_id=command.clinic_id)

        pending_schedules = self.schedule_repo.find_pending_by_channel(
            clinic_id=command.clinic_id, channel="letter"
        )

        if not pending_schedules:
            logger.info("letter_batch.no_pending_letters", clinic_id=command.clinic_id)
            return

        all_attachments = []
        schedules_by_attachment_name = {}
        clinic_name = ""

        for schedule in pending_schedules:
            try:
                context = self.context_builder.build(
                    patient_id=str(schedule.patient_id),
                    contract_id=str(schedule.contract_id),
                    clinic_id=str(schedule.clinic_id),
                )
                
                letter_stream = self.letter_notifier.letter_service.generate_letter(context)
                encoded_file = base64.b64encode(letter_stream.read()).decode()
                
                patient_name = context.get("patient_name", "paciente").replace(" ", "_")
                contract_id = context.get("contract_oralsin_id", "SN")
                clinic_name = self.clinic_repo.find_by_id(command.clinic_id).name
                
                attachment_name = f"Carta_{patient_name}_{contract_id}.docx"
                
                attachment = {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "contentBytes": encoded_file,
                    "name": attachment_name,
                }
                
                all_attachments.append(attachment)
                schedules_by_attachment_name[attachment_name] = schedule

            except Exception as e:
                logger.error("letter_batch.generation.failed", schedule_id=schedule.id, error=str(e))

        if not all_attachments:
            logger.warn("letter_batch.no_attachments_generated", clinic_id=command.clinic_id)
            return

        total_letters = len(all_attachments)
        
        for i in range(0, total_letters, BATCH_SIZE):
            attachment_batch = all_attachments[i:i + BATCH_SIZE]
            
            processed_schedules_batch = [
                schedules_by_attachment_name[att["name"]] for att in attachment_batch
            ]
            
            batch_number = (i // BATCH_SIZE) + 1
            total_batches = (total_letters + BATCH_SIZE - 1) // BATCH_SIZE
            
            logger.info(
                "letter_batch.sending_batch",
                clinic_id=command.clinic_id,
                batch_number=batch_number,
                total_batches=total_batches,
                batch_size=len(attachment_batch),
            )
            
            try:
                subject = (
                    f"Lote de Cartas ({batch_number}/{total_batches}) - "
                    f"Clínica {clinic_name} (Oralsin-DEBT)"
                )
                html_content = (
                    f"<p>Segue em anexo o lote {batch_number} de {total_batches}, "
                    f"contendo {len(attachment_batch)} cartas para impressão.</p>"
                )
                
                self.email_sender.send(
                    recipients=[BATCH_LETTER_RECIPIENT],
                    subject=subject,
                    html=html_content,
                    attachments=attachment_batch
                )
                logger.info("letter_batch.email.sent", batch=batch_number, count=len(attachment_batch))

                now = timezone.now()
                for schedule in processed_schedules_batch:
                    self.history_repo.save_from_schedule(
                        schedule=schedule,
                        success=True,
                        channel="letter",
                        sent_at=now,
                        observation=f"Enviado no lote {batch_number}/{total_batches} para {BATCH_LETTER_RECIPIENT}",
                    )
            
            except Exception as e:
                logger.error(
                    "letter_batch.email.failed",
                    batch=batch_number,
                    error=str(e),
                    exc_info=True,
                )
