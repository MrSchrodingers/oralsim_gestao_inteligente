from __future__ import annotations

from typing import Final

import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier
from notification_billing.core.application.dtos.whatsapp_notification_dto import WhatsappNotificationDTO

log = structlog.get_logger()


class DebtAppWhatsapp(BaseNotifier):
    """
    Adapter para envio de mensagens via DebtApp WhatsApp.

    Implementa `send_whatsapp()` exigido pela porta.
    """

    _DEFAULT_OPTIONS: Final[dict] = {
        "delay": 1200,
        "presence": "composing",
        "linkPreview": False,
    }

    def __init__(self, apikey: str, endpoint: str) -> None:
        super().__init__("debtapp", "whatsapp")
        self._apikey   = apikey
        self._endpoint = endpoint.rstrip("/")

    # ------------------------------------------------------------------
    # implementação da PORTA
    # ------------------------------------------------------------------
    def send(self, notification: WhatsappNotificationDTO) -> None:
        """
        Converte NotificationDTO → payload DebtApp e envia.
        """
        dto = WhatsappNotificationDTO(**notification.dict())
        self._send(
            number  = dto.to,
            text    = dto.message,
            options = dto.options,
        )

    # ------------------------------------------------------------------
    # utilitário interno
    # ------------------------------------------------------------------
    def _send(
        self,
        number: str,
        text: str,
        options: dict | None = None,
    ) -> None:
        if not number:
            return

        payload = {
            "number": number,
            "options": options or self._DEFAULT_OPTIONS,
            "textMessage": {"text": text},
        }

        self._request(
            "POST",
            self._endpoint,
            json=payload,
            headers={
                "apikey": self._apikey,
                "Content-Type": "application/json",
            },
        )
        log.info("whatsapp.sent", provider=self.provider, to=number)
