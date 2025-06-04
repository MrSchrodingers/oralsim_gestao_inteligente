from abc import ABC, abstractmethod

from notification_billing.core.domain.entities.message_entity import MessageEntity


class MessageRepository(ABC):
    @abstractmethod
    def find_default(self, channel: str, step: int) -> MessageEntity:
        """Retorna a mensagem default para canal e passo."""
        ...

    @abstractmethod
    def get_message(self, channel: str, step: int, clinic_id: str | None) -> MessageEntity | None:
        """Retorna mensagem custom para canal, passo e clínica, ou default."""
        ...
        
    @abstractmethod
    def find_custom(self, channel: str, step: int, clinic_id: str) -> MessageEntity | None:
        """Retorna mensagem custom para canal, passo e clínica, ou None."""
        ...

    @abstractmethod
    def save(self, message: MessageEntity) -> MessageEntity:
        """Cria ou atualiza uma mensagem."""
        ...

    @abstractmethod
    def delete(self, message_id: str) -> None:
        """Remove uma mensagem pelo ID."""
        ...
