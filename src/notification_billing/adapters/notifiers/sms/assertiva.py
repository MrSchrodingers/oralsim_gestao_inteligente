from __future__ import annotations

import base64
import io
import os
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()

try:
    from openpyxl import Workbook
except Exception as _e:
    Workbook = None


class AssertivaSMS(BaseNotifier):
    """
    Assertiva SMS

    - Em produção normal: usa OAuth2 client_credentials e envia via API.
    - Modo offline (default enquanto há bloqueio de IP): registra o lote,
      gera XLSX temporário e envia por e-mail usando o provider de Carta.

    Parâmetros:
    - auth_token: base64(client_id:client_secret) (quando online)
    - base_url: URL base da Assertiva
    - offline_reporter: callable(subject, html, attachments) -> None
      (attachments no formato Microsoft Graph fileAttachment)
    - force_offline: se True, SEMPRE usa a rota XLSX+email (ignora API)
      (ou defina env SMS_OFFLINE_MODE=1)
    """

    _TOKEN_LOCK = threading.Lock()

    def __init__(
        self,
        auth_token: str | None,
        base_url: str | None,
        offline_reporter: Callable[[str, str, list[dict]], None] | None = None,
        force_offline: bool | None = None,
    ):
        super().__init__("assertiva", "sms")

        # offline mode por env ou parâmetro explícito
        env_offline = os.getenv("SMS_OFFLINE_MODE", "").strip() in {"1", "true", "yes"}
        self._offline_only = bool(force_offline if force_offline is not None else env_offline or True)  # <- TRUE por enquanto

        self._basic_auth = (auth_token or "").strip()
        self._base_url = (base_url or "").rstrip("/")
        self._token: str | None = None
        self._token_exp: float = 0.0

        if not offline_reporter:
            # não geramos ciclo de import: o factory injeta isso
            raise ValueError("offline_reporter não fornecido (use o provider de Carta via factory)")

        self._offline_reporter = offline_reporter

        if self._offline_only:
            logger.warning("assertiva.offline_mode_enabled", reason="IP block / VPN pending")

    # ──────────────────────────────────────────────────────────
    # Interface pública
    # ──────────────────────────────────────────────────────────
    def send(self, phones: list[str], message: str) -> None:
        if not phones:
            return

        # Enquanto o IP está bloqueado, forçamos o fluxo offline.
        if self._offline_only:
            self._send_offline(phones, message)
            return

        # try:
        #     token = self._ensure_token()
        #     payload = {
        #         "can_receive_status": False,
        #         "can_receive_answer": False,
        #         "route_type": 1,
        #         "arraySms": [{"number": p, "message": message, "filter_value": "GestaoRecebiveis"} for p in phones],
        #     }
        #     self._request(
        #         "POST",
        #         f"{self._base_url}/sms/v3/send",
        #         json=payload,
        #         headers={
        #             "Authorization": f"Bearer {token}",
        #             "Accept": "application/json",
        #         },
        #     )
        #     logger.info("sms.sent", provider=self.provider, total=len(phones))
        # except Exception as e:
        #     logger.error("assertiva.api_failed_falling_back_offline", err=str(e))
        #     self._send_offline(phones, message)

        # Como o modo offline está ativo por padrão, chegaremos aqui apenas se você reativar o trecho acima.

    # ──────────────────────────────────────────────────────────
    # Helpers — OFFLINE
    # ──────────────────────────────────────────────────────────
    def _send_offline(self, phones: Iterable[str], message: str) -> None:
        """
        Gera um XLSX temporário com as linhas (timestamp_utc, phone, message)
        e envia por e-mail usando o provider de Carta (via offline_reporter).
        """
        if Workbook is None:
            raise RuntimeError(
                "openpyxl não está instalado. Instale com: pip install openpyxl"
            )

        ts = datetime.now(UTC)
        ts_str = ts.strftime("%Y-%m-%d_%H-%M-%S_UTC")
        rows = [(ts.isoformat(), p, message) for p in phones]

        # cria workbook em memória
        wb = Workbook()
        ws = wb.active
        ws.title = "sms_pendentes"
        ws.append(["timestamp_utc", "phone", "message"])
        for r in rows:
            ws.append(list(r))

        # escreve XLSX num arquivo temporário (também preservamos em bytes)
        with tempfile.NamedTemporaryFile(prefix="sms_offline_", suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
            wb.save(tmp_path)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        xlsx_bytes = buf.read()
        xlsx_b64 = base64.b64encode(xlsx_bytes).decode("ascii")

        attachment = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": f"sms_offline_{ts_str}.xlsx",
            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "contentBytes": xlsx_b64,
        }

        subject = f"[SMS OFFLINE] {len(rows)} mensagens pendentes — {ts_str}"
        html = (
            f"<p>Gerado automaticamente em {ts_str}.</p>"
            f"<p>Total de mensagens: <b>{len(rows)}</b></p>"
            "<p>Arquivo em anexo contendo colunas: <code>timestamp_utc, phone, message</code>.</p>"
            "<p>Motivo: bloqueio de IP no provedor Assertiva. Enviar manualmente pelo canal local.</p>"
        )

        try:
            self._offline_reporter(subject, html, [attachment])
            logger.info("sms.offline_report_sent", total=len(rows), path=tmp_path)
        except Exception as e:
            logger.error("sms.offline_report_failed", err=str(e), path=tmp_path)
            # mesmo se o envio falhar, mantemos o arquivo temporário no disco para resgate manual

    # ──────────────────────────────────────────────────────────
    # Helpers — ONLINE (mantidos para quando reativar)
    # ──────────────────────────────────────────────────────────
    def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_exp:
            return self._token

        with AssertivaSMS._TOKEN_LOCK:
            if self._token and now < self._token_exp:
                return self._token

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

            data = response.json()
            access_token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            if not access_token:
                raise RuntimeError(f"Token inválido. Resposta: {data}")

            self._token = access_token
            self._token_exp = time.time() + max(30, expires_in - 10)
            logger.info("assertiva.token_refreshed", expires_in=expires_in)
            return self._token
