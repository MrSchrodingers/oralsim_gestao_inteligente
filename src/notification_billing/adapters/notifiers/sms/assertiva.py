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
    * Timeout padrão e retry exponencial herdados de BaseNotifier.
    """

    _TOKEN_LOCK = threading.Lock()

    def __init__(self, auth_token: str, base_url: str):
        super().__init__("assertiva", "sms")
        self._basic_auth = auth_token
        self._base_url = base_url.rstrip("/")
        self._host = self._base_url.replace("https://", "")

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
        
        # 1. Converte o payload para uma string JSON e depois para bytes para calcular o tamanho
        payload_str = json.dumps(payload)
        payload_bytes = payload_str.encode('utf-8')
        
        self._request(
            "POST",
            f"{self._base_url}/sms/v3/send",
            # 2. Usa o parâmetro 'content' para enviar os dados brutos
            content=payload_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Host": self._host,
                "Content-Length": str(len(payload_bytes)),
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

            # 1. Prepara os dados e cabeçalhos manualmente
            data_to_send = "grant_type=client_credentials"
            data_bytes = data_to_send.encode('utf-8')

            response = self._request(
                "POST",
                f"{self._base_url}/oauth2/v3/token",
                # 2. Usa o parâmetro 'content'
                content=data_bytes,
                headers={
                    "Authorization": f"Basic {self._token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Host": self._host,
                    "Content-Length": str(len(data_bytes)),
                },
            )
            data = response.json()
            self._token = data["access_token"]
            self._token_exp = time.time() + data.get("expires_in", 3600) - 10
            logger.info("assertiva.token_refreshed")
            return self._token