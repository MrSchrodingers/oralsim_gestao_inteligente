# adapters/notifiers/sms/assertiva.py
from __future__ import annotations

import base64
import io
import os
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()

try:
    from openpyxl import Workbook
except Exception as _e:  # pragma: no cover
    Workbook = None


class AssertivaSMS(BaseNotifier):
    """
    Assertiva SMS

    - Enquanto o IP estiver bloqueado, opera em modo OFFLINE:
      * send(): APENAS ACUMULA as linhas (não envia API, não manda e-mail).
      * flush_offline_buffer(): gera UM XLSX com TODOS os registros acumulados
        e envia UM ÚNICO E-MAIL via provider de Carta.

    - Quando voltar ao modo online, reative a chamada da API na função send().

    Parâmetros:
    - auth_token: base64(client_id:client_secret) (para modo online futuro)
    - base_url: URL base da Assertiva
    - offline_reporter: callable(subject, html, attachments) -> None
        (attachments no formato Microsoft Graph fileAttachment)
    - force_offline: força o modo offline. Default: True neste período.
    """

    _TOKEN_LOCK = threading.Lock()

    # ---- Buffer global (process-wide) para acumular registros offline ----
    _OFFLINE_LOCK = threading.Lock()
    _OFFLINE_BUFFER: list[tuple[str, str, str]] = []  # (timestamp_iso, phone, message)
    _OFFLINE_REPORTER: Callable[[str, str, list[dict]], None] | None = None

    def __init__(
        self,
        auth_token: str | None,
        base_url: str | None,
        offline_reporter: Callable[[str, str, list[dict]], None] | None = None,
        force_offline: bool | None = None,
    ):
        super().__init__("assertiva", "sms")

        env_offline = os.getenv("SMS_OFFLINE_MODE", "").strip().lower() in {"1", "true", "yes"}
        # Enquanto o VPN não está ativo, deixamos True
        self._offline_only = bool(force_offline if force_offline is not None else (env_offline or True))

        self._basic_auth = (auth_token or "").strip()
        self._base_url = (base_url or "").rstrip("/")
        self._token: str | None = None
        self._token_exp: float = 0.0

        if offline_reporter is None:
            raise ValueError("offline_reporter não fornecido (injete via factory usando o provider de Carta)")
        # guarda o reporter em nível de classe (flush é classmethod)
        AssertivaSMS._OFFLINE_REPORTER = offline_reporter

        if self._offline_only:
            logger.warning("assertiva.offline_mode_enabled", reason="IP block / usando relatório XLSX único")

    # ──────────────────────────────────────────────────────────
    # Interface pública
    # ──────────────────────────────────────────────────────────
    def send(self, phones: list[str], message: str) -> None:
        """
        MODO OFFLINE: acumula registros no buffer global.
        (Cada phone vira uma linha separada no XLSX final.)
        """
        if not phones:
            return

        if self._offline_only:
            ts = datetime.now(UTC).isoformat()
            with AssertivaSMS._OFFLINE_LOCK:
                for p in phones:
                    AssertivaSMS._OFFLINE_BUFFER.append((ts, p, message))
            logger.info("sms.offline_buffer_append", added=len(phones), total=len(AssertivaSMS._OFFLINE_BUFFER))
            return

        # ====== (modo online — comentado por enquanto) ======
        # token = self._ensure_token()
        # payload = {
        #     "can_receive_status": False,
        #     "can_receive_answer": False,
        #     "route_type": 1,
        #     "arraySms": [{"number": p, "message": message, "filter_value": "GestaoRecebiveis"} for p in phones],
        # }
        # self._request(
        #     "POST",
        #     f"{self._base_url}/sms/v3/send",
        #     json=payload,
        #     headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        # )
        # logger.info("sms.sent", provider=self.provider, total=len(phones))

    # ──────────────────────────────────────────────────────────
    # Flush único (gera XLSX e envia 1 e-mail)
    # ──────────────────────────────────────────────────────────
    @classmethod
    def flush_offline_buffer(cls, subject_prefix: str = "[SMS OFFLINE]") -> tuple[int, str | None]:
        """
        Gera UM XLSX com TODO o buffer acumulado e envia UM e-mail via reporter.
        Retorna (total_linhas, caminho_arquivo_temporario_ou_None).

        Se o buffer estiver vazio, não envia nada e retorna (0, None).
        """
        if Workbook is None:
            raise RuntimeError("openpyxl não instalado. Instale: pip install openpyxl")

        with cls._OFFLINE_LOCK:
            rows = list(cls._OFFLINE_BUFFER)
            cls._OFFLINE_BUFFER.clear()

        if not rows:
            logger.info("sms.offline_buffer_empty")
            return 0, None

        # monta XLSX
        ts = datetime.now(UTC)
        ts_str = ts.strftime("%Y-%m-%d_%H-%M-%S_UTC")

        wb = Workbook()
        ws = wb.active
        ws.title = "sms_pendentes"
        ws.append(["timestamp_utc", "phone", "message"])
        for (t, phone, msg) in rows:
            ws.append([t, phone, msg])

        # grava em arquivo temporário (mantemos uma cópia em disco p/ auditoria)
        with tempfile.NamedTemporaryFile(prefix="sms_offline_", suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
            wb.save(tmp_path)

        # gera bytes para anexo (Graph usa base64)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        xlsx_b64 = base64.b64encode(buf.read()).decode("ascii")

        attach = [{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": f"sms_offline_{ts_str}.xlsx",
            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "contentBytes": xlsx_b64,
        }]

        subject = f"{subject_prefix} {len(rows)} mensagens pendentes — {ts_str}"
        html = (
            f"<p>Relatório único de SMS offline gerado em {ts_str}.</p>"
            f"<p>Total de mensagens: <b>{len(rows)}</b></p>"
            "<p>Arquivo em anexo com colunas: <code>timestamp_utc, phone, message</code>.</p>"
            "<p>Motivo: bloqueio de IP no provedor Assertiva. Executar envio manual local.</p>"
        )

        reporter = cls._OFFLINE_REPORTER
        if not reporter:
            logger.error("sms.offline_reporter_missing")
            return len(rows), tmp_path

        try:
            reporter(subject, html, attach)
            logger.info("sms.offline_report_sent", total=len(rows), path=tmp_path)
        except Exception as e:  # pragma: no cover
            logger.error("sms.offline_report_failed", err=str(e), path=tmp_path)
            # arquivo fica no disco para resgate manual
        return len(rows), tmp_path

    # ──────────────────────────────────────────────────────────
    # (mantido para o futuro modo online)
    # ──────────────────────────────────────────────────────────
    def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_exp:
            return self._token
        with AssertivaSMS._TOKEN_LOCK:
            if self._token and now < self._token_exp:
                return self._token
            resp = self._request(
                "POST",
                f"{self._base_url}/oauth2/v3/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {self._basic_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )
            data = resp.json()
            tok = data.get("access_token")
            exp = int(data.get("expires_in", 3600))
            if not tok:
                raise RuntimeError(f"Token inválido. Resposta: {data}")
            self._token = tok
            self._token_exp = time.time() + max(30, exp - 10)
            logger.info("assertiva.token_refreshed", expires_in=exp)
            return self._token
