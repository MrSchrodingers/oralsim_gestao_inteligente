from __future__ import annotations

import json
import threading
import time

import structlog
from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()

class AssertivaSMS(BaseNotifier):
    """
    Adapter para o serviço Assertiva SMS.
    * Refresh de token OAuth2 (client-credentials) é thread-safe.
    * Timeout e retry herdados de BaseNotifier.
    """

    _TOKEN_LOCK = threading.Lock()

    def __init__(self, auth_token: str, base_url: str):
        super().__init__("assertiva", "sms")
        if not auth_token:
            raise ValueError("ASSERTIVA_AUTH_TOKEN não definido")
        if not base_url:
            raise ValueError("ASSERTIVA_BASE_URL não definido")

        self._basic_auth = auth_token.strip()  # base64(client_id:client_secret)
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._token_exp: float = 0.0

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

        # Envia como JSON (deixe httpx serializar e calcular o Content-Length)
        self._request(
            "POST",
            f"{self._base_url}/sms/v3/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
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
            if self._token and now < self._token_exp:  # race-check
                return self._token

            # Usa x-www-form-urlencoded com auth Basic CORRETO
            response = self._request(
                "POST",
                f"{self._base_url}/oauth2/v3/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {self._basic_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

            # Se houver 4xx/5xx, BaseNotifier._request deve levantar; logue o corpo para diagnóstico
            data = response.json()

            access_token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            if not access_token:
                raise RuntimeError(f"Token inválido. Resposta: {data}")

            # Guarda com pequena folga
            self._token = access_token
            self._token_exp = time.time() + max(30, expires_in - 10)
            logger.info("assertiva.token_refreshed", expires_in=expires_in)
            return self._token
