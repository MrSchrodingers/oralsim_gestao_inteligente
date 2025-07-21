import uuid
from datetime import datetime

# Commands
from notification_billing.core.application.commands.contact_schedule_commands import CreateContactScheduleCommand, DeleteContactScheduleCommand, UpdateContactScheduleCommand
from notification_billing.core.application.commands.message_commands import CreateMessageCommand, DeleteMessageCommand, UpdateMessageCommand
from notification_billing.core.application.cqrs import CommandHandler

# Entities
from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity
from notification_billing.core.domain.entities.message_entity import MessageEntity

# Repositories
from notification_billing.core.domain.repositories.contact_schedule_repository import ContactScheduleRepository
from notification_billing.core.domain.repositories.message_repository import MessageRepository

# ——— CONTACT SCHEDULE ———————————————————————————————————————

class CreateContactScheduleHandler(CommandHandler[CreateContactScheduleCommand]):
    def __init__(self, repo: ContactScheduleRepository):
        self.repo = repo

    def handle(self, command: CreateContactScheduleCommand) -> ContactScheduleEntity:
        data = command.payload.dict()
        data['id'] = uuid.uuid4()
        data.setdefault('scheduled_date', datetime.utcnow())
        entity = ContactScheduleEntity.from_dict(data)
        return self.repo.save(entity)

class UpdateContactScheduleHandler(CommandHandler[UpdateContactScheduleCommand]):
    def __init__(self, repo: ContactScheduleRepository):
        self.repo = repo

    def handle(self, command: UpdateContactScheduleCommand) -> ContactScheduleEntity:
        data = command.payload.dict()
        data['id'] = command.id
        entity = ContactScheduleEntity.from_dict(data)
        return self.repo.save(entity)

class DeleteContactScheduleHandler(CommandHandler[DeleteContactScheduleCommand]):
    def __init__(self, repo: ContactScheduleRepository):
        self.repo = repo

    def handle(self, command: DeleteContactScheduleCommand) -> None:
        self.repo.delete(command.id)


# ——— MESSAGE ——————————————————————————————————————————————

class CreateMessageHandler(CommandHandler[CreateMessageCommand]):
    def __init__(self, repo: MessageRepository):
        self.repo = repo

    def handle(self, command: CreateMessageCommand) -> MessageEntity:
        data = command.payload.dict()
        data['id'] = uuid.uuid4()
        entity = MessageEntity.from_dict(data)
        return self.repo.save(entity)

class UpdateMessageHandler(CommandHandler[UpdateMessageCommand]):
    def __init__(self, repo: MessageRepository):
        self.repo = repo

    def handle(self, command: UpdateMessageCommand) -> MessageEntity:
        data = command.payload.dict()
        data['id'] = command.id
        entity = MessageEntity.from_dict(data)
        return self.repo.save(entity)

class DeleteMessageHandler(CommandHandler[DeleteMessageCommand]):
    def __init__(self, repo: MessageRepository):
        self.repo = repo

    def handle(self, command: DeleteMessageCommand) -> None:
        self.repo.delete(command.id)