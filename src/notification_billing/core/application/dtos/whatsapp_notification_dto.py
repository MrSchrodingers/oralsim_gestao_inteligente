from typing import Any

from pydantic import BaseModel


class WhatsappNotificationDTO(BaseModel):
    """
    Data Transfer Object for WhatsApp notifications.
    """
    to: str  # Recipient's phone number
    message: str  # Message content
    options: dict[str, Any] | None = None 