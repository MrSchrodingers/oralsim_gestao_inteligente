from dataclasses import dataclass

from notification_billing.core.application.cqrs import CommandDTO
from notification_billing.core.application.dtos.message_dto import MessageDTO


@dataclass(frozen=True)
class CreateMessageCommand(CommandDTO):
    payload: MessageDTO

@dataclass(frozen=True)
class UpdateMessageCommand(CommandDTO):
    id: str
    payload: MessageDTO

@dataclass(frozen=True)
class DeleteMessageCommand(CommandDTO):
    id: str
