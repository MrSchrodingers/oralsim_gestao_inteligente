import threading
import uuid

from django.core.management import call_command
from oralsin_core.adapters.security.hash_service import HashService
from oralsin_core.core.application.commands.registration_request_commands import ApproveRegistrationRequestCommand, CreateRegistrationRequestCommand, RejectRegistrationRequestCommand
from oralsin_core.core.application.commands.user_commands import CreateUserCommand
from oralsin_core.core.application.cqrs import CommandBus, CommandHandler, PagedResult, QueryHandler
from oralsin_core.core.application.dtos.user_dto import CreateUserDTO
from oralsin_core.core.application.queries.registration_request_queries import GetRegistrationRequestQuery, ListRegistrationRequestsQuery
from oralsin_core.core.domain.entities.registration_request_entity import RegistrationRequestEntity
from oralsin_core.core.domain.repositories.registration_request_repository import RegistrationRequestRepository

from plugins.django_interface.models import Clinic as ClinicModel


class CreateRegistrationRequestHandler(CommandHandler[CreateRegistrationRequestCommand]):
    def __init__(self, repo: RegistrationRequestRepository, hash_service: HashService):
        self.repo = repo
        self.hash_service = hash_service

    def handle(self, command: CreateRegistrationRequestCommand) -> RegistrationRequestEntity:
        data = command.payload.dict()
        hashed_password = self.hash_service.hash_password(data.pop('password'))
        entity = RegistrationRequestEntity(
            id=uuid.uuid4(),
            password_hash=hashed_password,
            **data
        )
        return self.repo.save(entity)

class ApproveRegistrationRequestHandler(CommandHandler[ApproveRegistrationRequestCommand]):
    def __init__(self, repo: RegistrationRequestRepository, command_bus: CommandBus):
        self.repo = repo
        self.command_bus = command_bus
        
    def _run_background_syncs(self, clinic_name: str, oralsin_clinic_id: int):
        """
        Esta função encapsula os comandos de longa duração
        e será executada em uma thread separada.
        """
        try:
            print(f"[THREAD] Iniciando sincronização para a clínica ID: {oralsin_clinic_id}...")
            
            call_command('sync_old_debts', clinic_id=oralsin_clinic_id)
            print(f"[THREAD] 'sync_old_debts' para '{clinic_name}' concluído.")
            
            call_command('sync_acordo_activities', clinic_id=oralsin_clinic_id)
            print(f"[THREAD] 'sync_acordo_activities' para '{clinic_name}' concluído.")
            
            call_command('seed_scheduling', clinic_id=oralsin_clinic_id)
            print(f"[THREAD] 'seed_scheduling' para '{clinic_name}' concluído.")

            print(f"[THREAD] Sincronização em background para a clínica '{clinic_name}' finalizada com sucesso.")
        except Exception as e:
            print(f"[THREAD-ERROR] Falha durante a sincronização para '{clinic_name}': {e}")

    def handle(self, command: ApproveRegistrationRequestCommand) -> RegistrationRequestEntity:
        request = self.repo.find_by_id(command.request_id)
        if not request or request.status != 'pending':
            raise ValueError("Solicitação de registro não encontrada ou em estado inválido.")

        # Passos 1 a 4 (que já estavam funcionando)
        request.status = 'approved'
        self.repo.save(request)
        
        call_command(
            'seed_data',
            clinic_name=request.clinic_name,
            owner_name=request.name,
            min_days_billing=request.cordial_billing_config,
            skip_admin=True,
            skip_clinic_user=True,
            skip_full_sync=True,
        )

        try:
            clinic_model = ClinicModel.objects.get(name=request.clinic_name)
            clinic_id = clinic_model.id
            oralsin_clinic_id = clinic_model.oralsin_clinic_id
        except ClinicModel.DoesNotExist:
            print(f"ERRO CRÍTICO: Não foi possível encontrar a clínica '{request.clinic_name}' após o seed.")
            raise ValueError("Falha ao configurar a clínica.")

        user_dto = CreateUserDTO(
            email=request.email, password_hash=request.password_hash,
            name=request.name, role="clinic", clinic_id=str(clinic_id)
        )
        self.command_bus.dispatch(CreateUserCommand(payload=user_dto))
        
        # 3. Disparar a função de sync em uma nova thread
        print(f"Agendando comandos de sincronização para '{request.clinic_name}' em background...")
        sync_thread = threading.Thread(
            target=self._run_background_syncs,
            args=(request.clinic_name, oralsin_clinic_id)
        )
        sync_thread.start() 

        return request

class RejectRegistrationRequestHandler(CommandHandler[RejectRegistrationRequestCommand]):
    def __init__(self, repo: RegistrationRequestRepository):
        self.repo = repo

    def handle(self, command: RejectRegistrationRequestCommand) -> RegistrationRequestEntity:
        request = self.repo.find_by_id(command.request_id)
        if not request or request.status != 'pending':
            raise ValueError("Registration request not found or not pending.")
        
        request.status = 'rejected'
        return self.repo.save(request)

class ListRegistrationRequestsHandler(QueryHandler[ListRegistrationRequestsQuery, PagedResult[RegistrationRequestEntity]]):
    def __init__(self, repo: RegistrationRequestRepository):
        self.repo = repo

    def handle(self, query: ListRegistrationRequestsQuery) -> PagedResult[RegistrationRequestEntity]:
        return self.repo.list(query.filtros, query.page, query.page_size)

class GetRegistrationRequestHandler(QueryHandler[GetRegistrationRequestQuery, RegistrationRequestEntity]):
    def __init__(self, repo: RegistrationRequestRepository):
        self.repo = repo

    def handle(self, query: GetRegistrationRequestQuery) -> RegistrationRequestEntity:
        return self.repo.find_by_id(query.request_id)