# notification_billing/adapters/notifiers/email/brevo.py

from __future__ import annotations

import httpx
import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()

class BrevoEmail(BaseNotifier):
    """
    Envia e-mails HTML usando a API Brevo Transactional Emails v3.
    """

    def __init__(self, api_key: str, from_email: str):
        super().__init__("brevo", "email")
        self._api_key    = api_key
        self._from_email = from_email
        self._endpoint   = "https://api.brevo.com/v3/smtp/email"

    def send(
        self,
        recipients: list[str],
        subject: str,
        html: str,
        attachments: list[dict] | None = None,
    ) -> None:
        """
        Envia um e-mail transacional via Brevo.

        - recipients: lista de e-mails (até 99 destinatários) :contentReference[oaicite:6]{index=6}
        - subject: assunto do e-mail
        - html: conteúdo HTML
        - attachments: lista de dicionários no formato Brevo (url ou content) :contentReference[oaicite:7]{index=7}
        """
        try:
            if not recipients:
                return

            payload = {
                "sender":     {"email": self._from_email},   # remete ao DEFAULT_FROM_EMAIL :contentReference[oaicite:8]{index=8}
                "to":         [{"email": r} for r in recipients],
                "subject":    subject,
                "htmlContent": html,
            }

            if attachments:
                # Parâmetro de anexos conforme changelog Brevo :contentReference[oaicite:9]{index=9}
                payload["attachment"] = attachments

            # Cabeçalhos de autenticação e conteúdo :contentReference[oaicite:10]{index=10}
            headers = {
                "api-key":       self._api_key,
                "accept":        "application/json",
                "content-type":  "application/json",
            }

            # Uso do método unificado de request (timeout, retry, métricas)
            _response = self._request(
                "POST",
                self._endpoint,
                json=payload,
                headers=headers,
            )

            logger.info(
                "email.sent",
                provider=self.provider,
                from_=self._from_email,
                recipients=len(recipients),
                subject=subject,
            )

        except httpx.HTTPStatusError as exc:
            # Tratamento de erro com extração de detalhe JSON ou texto
            resp = exc.response
            detail = None
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text

            logger.error(
                "brevo.error",
                status=resp.status_code,
                detail=detail,
            )
            raise
