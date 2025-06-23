import uuid
from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.registration_request_dto import CreateRegistrationRequestDTO


@dataclass(frozen=True)
class CreateRegistrationRequestCommand(CommandDTO):
    payload: CreateRegistrationRequestDTO

@dataclass(frozen=True)
class ApproveRegistrationRequestCommand(CommandDTO):
    request_id: uuid.UUID

@dataclass(frozen=True)
class RejectRegistrationRequestCommand(CommandDTO):
    request_id: uuid.UUID