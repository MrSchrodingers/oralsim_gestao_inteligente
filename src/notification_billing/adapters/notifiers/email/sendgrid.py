from __future__ import annotations

import httpx
import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()


class SendGridEmail(BaseNotifier):
    """
    Envia e-mails HTML utilizando a API SendGrid (v3).

    * Usa httpx para manter timeout/retry unificados.
    * Suporta anexos binários via parâmetro opcional `attachments`
      no formato exigido pelo SendGrid (dicts base64).
    """

    def __init__(self, api_key: str, from_email: str):
        super().__init__("sendgrid", "email")
        self._api_key    = api_key
        self._from_email = from_email
        self._endpoint   = "https://api.sendgrid.com/v3/mail/send"

    # ──────────────────────────────────────────────────────────
    # API
    # ──────────────────────────────────────────────────────────
    def send(
        self,
        recipients: list[str],
        subject: str,
        html: str,
        attachments: list[dict] | None = None,
    ) -> None:
        
        try: 
            if not recipients:
                return

            payload = {
                "from": {"email": self._from_email},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
                "personalizations": [{"to": [{"email": r} for r in recipients]}],
            }
            if attachments:
                payload["attachments"] = attachments

            self._request(
                "POST",
                self._endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            logger.info(
                "email.sent",
                provider=self.provider,
                from_=self._from_email,
                recipients=len(recipients),
                subject=subject,
            )
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text
            logger.error(
                "sendgrid.error",
                status=exc.response.status_code,
                detail=detail,
            )
            raise
