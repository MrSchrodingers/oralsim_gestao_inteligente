from dataclasses import dataclass

from notification_billing.core.application.cqrs import CommandDTO
from notification_billing.core.application.dtos.schedule_dto import ContactScheduleDTO


@dataclass(frozen=True)
class CreateContactScheduleCommand(CommandDTO):
    payload: ContactScheduleDTO

@dataclass(frozen=True)
class UpdateContactScheduleCommand(CommandDTO):
    id: str
    payload: ContactScheduleDTO

@dataclass(frozen=True)
class DeleteContactScheduleCommand(CommandDTO):
    id: str
