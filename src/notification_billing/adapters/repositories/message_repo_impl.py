from django.core.exceptions import ObjectDoesNotExist

from notification_billing.core.domain.entities.message_entity import MessageEntity
from notification_billing.core.domain.repositories.message_repository import MessageRepository
from plugins.django_interface.models import Message as MessageModel


class MessageRepoImpl(MessageRepository):
    def find_default(self, channel: str, step: int) -> MessageEntity:
        try:
            m = MessageModel.objects.get(
                type=channel, step=step, is_default=True
            )
            return MessageEntity.from_model(m)
        except ObjectDoesNotExist:
            return None

    def find_custom(self, channel: str, step: int, clinic_id: str) -> MessageEntity | None:
        m = MessageModel.objects.filter(type=channel, step=step, clinic_id=clinic_id).first()
        return MessageEntity.from_model(m) if m else None

    def save(self, message: MessageEntity) -> MessageEntity:
        m, _ = MessageModel.objects.update_or_create(
            id=message.id,
            defaults=message.to_dict()
        )
        return MessageEntity.from_model(m)
    
    def get_message(self, channel: str, step: int, clinic_id: str | None) -> MessageEntity | None:
        msg = self.find_custom(channel, step, clinic_id)
        if msg is not None:
            return msg
        return self.find_default(channel, step)

    def delete(self, message_id: str) -> None:
        MessageModel.objects.filter(id=message_id).delete()
