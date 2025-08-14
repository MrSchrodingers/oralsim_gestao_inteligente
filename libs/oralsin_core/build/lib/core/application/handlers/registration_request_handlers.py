import uuid

from cryptography.fernet import Fernet

from config import settings
from oralsin_core.adapters.message_broker.rabbitmq import MessagingService, registration_exchange
from oralsin_core.adapters.security.hash_service import HashService
from oralsin_core.core.application.commands.registration_request_commands import ApproveRegistrationRequestCommand, CreateRegistrationRequestCommand, RejectRegistrationRequestCommand
from oralsin_core.core.application.cqrs import CommandHandler, PagedResult, QueryHandler
from oralsin_core.core.application.queries.registration_request_queries import GetRegistrationRequestQuery, ListRegistrationRequestsQuery
from oralsin_core.core.domain.entities.registration_request_entity import RegistrationRequestEntity
from oralsin_core.core.domain.repositories.registration_request_repository import RegistrationRequestRepository

FERNET = Fernet(settings.REGISTRATION_KEY)

class CreateRegistrationRequestHandler(CommandHandler[CreateRegistrationRequestCommand]):
    def __init__(self, repo: RegistrationRequestRepository, hash_service: HashService):
        self.repo = repo
        self.hash_service = hash_service

    def handle(self, command: CreateRegistrationRequestCommand):
        data = command.payload.dict()
        raw_password   = data.pop("password")
        hashed_password = self.hash_service.hash_password(raw_password)

        entity = RegistrationRequestEntity(
            id=uuid.uuid4(),
            password_hash=hashed_password,
            password_enc=FERNET.encrypt(raw_password.encode()).decode(),
            **data,
        )
        return self.repo.save(entity)


class ApproveRegistrationRequestHandler(CommandHandler[ApproveRegistrationRequestCommand]):
    def __init__(self, repo: RegistrationRequestRepository, messaging_service: MessagingService):
        self.repo = repo
        self.messaging_service = messaging_service

    def handle(self, command: ApproveRegistrationRequestCommand) -> RegistrationRequestEntity:
        request = self.repo.find_by_id(command.request_id)
        if not request or request.status != 'pending':
            raise ValueError("Solicitação de registro não encontrada ou em estado inválido.")

        request.status = 'approved'
        self.repo.save(request)
        
        message_payload = {
            "request_id": str(request.id),
            "clinic_name": request.clinic_name,
            "name": request.name,
            "email": request.email,
            "password": command.raw_password,
            "cordial_billing_config": request.cordial_billing_config,
        }
        
        self.messaging_service.publish(
            exchange=registration_exchange,
            routing_key="approved",
            message=message_payload
        )
        
        print(f"Pipeline de configuração para a clínica '{request.clinic_name}' agendado com sucesso.")
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