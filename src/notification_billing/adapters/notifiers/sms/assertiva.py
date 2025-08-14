from __future__ import annotations

import base64
import threading
import time

import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()

class AssertivaSMS(BaseNotifier):
    """
    Adapter para o serviço Assertiva SMS.

    * Refresh de token OAuth2 (client-credentials) é thread-safe.
    * Timeout padrão e retry exponencial herdados de BaseNotifier.
    """

    _TOKEN_LOCK = threading.Lock()

    def __init__(self, auth_token: str, base_url: str):
        super().__init__("assertiva", "sms")
        self._basic_auth    = auth_token
        self._base_url      = base_url.rstrip("/")

        self._token: str | None = None
        self._token_exp: float  = 0.0   # epoch segundos

    # ──────────────────────────────────────────────────────────
    # Interface pública
    # ──────────────────────────────────────────────────────────
    def send(self, phones: list[str], message: str) -> None:
        if not phones:
            return

        token = self._ensure_token()
        payload = {
            "can_receive_status": False,
            "can_receive_answer": False,
            "route_type": 1,
            "arraySms": [
                {"number": p, "message": message, "filter_value": "GestaoRecebiveis"}
                for p in phones
            ],
        }

        self._request(
            "POST",
            f"{self._base_url}/sms/v3/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        logger.info("sms.sent", provider=self.provider, total=len(phones))

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────
    def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_exp:
            return self._token

        with AssertivaSMS._TOKEN_LOCK:
            if self._token and now < self._token_exp:          # race-check
                return self._token
            auth_bytes = self._basic_auth.encode("utf-8")
            base64_auth = base64.b64encode(auth_bytes).decode("utf-8")
            
            response = self._request(
                "POST",
                f"{self._base_url}/oauth2/v3/token",
                data="grant_type=client_credentials",
                headers={
                    "Authorization": f"Basic {base64_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            data = response.json()
            self._token      = data["access_token"]
            self._token_exp  = time.time() + data.get("expires_in", 3600) - 10
            logger.info("assertiva.token_refreshed")
            return self._token
