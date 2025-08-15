# adapters/notifiers/sms/assertiva.py
from __future__ import annotations

import base64
import io
import os
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from notification_billing.adapters.notifiers.base import BaseNotifier

logger = structlog.get_logger()

try:
    from openpyxl import Workbook
except Exception as _e:  # pragma: no cover
    Workbook = None


@dataclass
class _BuiltXLSX:
    name: str
    blob: bytes
    rows: int
    path: str  # caminho real do arquivo temporário salvo (auditoria)


class AssertivaSMS(BaseNotifier):
    """
    Assertiva SMS

    - Enquanto o IP estiver bloqueado, opera em modo OFFLINE:
      * send(): APENAS ACUMULA as linhas (não envia API, não manda e-mail).
      * flush_offline_buffer(): divide em LOTES se necessário, gerando 1..N XLSX
        e enviando 1..M e-mails via provider de Carta, respeitando limites.

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

    # ---------- Limites configuráveis (com defaults seguros) ----------
    # Tamanho alvo por ARQUIVO (bytes). Padrão 8 MiB ~ bem abaixo de 25 MiB com folga.
    _FILE_MAX_BYTES = int(os.getenv("SMS_OFFLINE_FILE_MAX_BYTES", str(8 * 1024 * 1024)))
    # Máximo de LINHAS por arquivo (limite lógico para dividir trabalhos grandes)
    _FILE_MAX_ROWS = int(os.getenv("SMS_OFFLINE_FILE_MAX_ROWS", "10000"))

    # Limites por E-MAIL
    _EMAIL_MAX_ATTACH = int(os.getenv("SMS_OFFLINE_EMAIL_MAX_ATTACH", "5"))
    _EMAIL_MAX_BYTES = int(os.getenv("SMS_OFFLINE_EMAIL_MAX_BYTES", str(20 * 1024 * 1024)))  # 20 MiB

    # ---------- Autoflush ----------
    _AUTOFLUSH_MIN_ROWS = int(os.getenv("SMS_OFFLINE_AUTOFLUSH_MIN_ROWS", "1000"))  # dispara por volume
    _AUTOFLUSH_MAX_AGE_SEC = int(os.getenv("SMS_OFFLINE_AUTOFLUSH_MAX_AGE_SEC", "600"))  # dispara por tempo

    _LAST_FLUSH_TS: float = 0.0
    _FLUSHING = False
    _FLUSH_LOCK = threading.Lock()

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

        if AssertivaSMS._LAST_FLUSH_TS == 0.0:
            AssertivaSMS._LAST_FLUSH_TS = time.time()

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
                total = len(AssertivaSMS._OFFLINE_BUFFER)
            logger.info("sms.offline_buffer_append", added=len(phones), total=total)
            # tenta disparar autoflush não-bloqueante
            AssertivaSMS._maybe_autoflush()
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
    # Flush (gera 1..N XLSX e envia 1..M e-mails em lotes)
    # ──────────────────────────────────────────────────────────
    @classmethod
    def flush_offline_buffer(cls, subject_prefix: str = "[SMS OFFLINE]") -> tuple[int, str | None]:
        """
        Divide em lotes automaticamente:
        - fatia as linhas em múltiplos ARQUIVOS respeitando:
            * FILE_MAX_ROWS
            * FILE_MAX_BYTES
        - agrupa os anexos em 1..N E-MAILS respeitando:
            * EMAIL_MAX_ATTACH
            * EMAIL_MAX_BYTES (tamanho total dos anexos do e-mail)

        Retorna (total_linhas, caminho_de_um_tempfile_qualquer_ou_None).

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

        total = len(rows)
        ts_master = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S_UTC")

        # 1) Criar anexos (1..K arquivos) dentro dos limites por ARQUIVO
        files: list[_BuiltXLSX] = cls._chunk_rows_into_files(rows, ts_master)

        # 2) Enviar 1..M e-mails agrupando anexos por limites por E-MAIL
        sent_emails, sample_path = cls._send_files_in_batched_emails(files, subject_prefix, ts_master, total)

        logger.info(
            "sms.offline_report_sent_batched",
            total_rows=total,
            total_files=len(files),
            emails_sent=sent_emails,
            sample_path=sample_path,
        )
        cls._LAST_FLUSH_TS = time.time()
        return total, sample_path

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

    # ──────────────────────────────────────────────────────────
    # Autoflush helpers
    # ──────────────────────────────────────────────────────────
    @classmethod
    def _maybe_autoflush(cls) -> None:
        now = time.time()
        with cls._OFFLINE_LOCK:
            size = len(cls._OFFLINE_BUFFER)
        age = now - cls._LAST_FLUSH_TS

        if size >= cls._AUTOFLUSH_MIN_ROWS or age >= cls._AUTOFLUSH_MAX_AGE_SEC:
            # evita flush concorrente
            if cls._FLUSHING:
                return
            t = threading.Thread(target=cls._run_autoflush, name="assertiva_sms_autoflush", daemon=True)
            t.start()

    @classmethod
    def _run_autoflush(cls) -> None:
        with cls._FLUSH_LOCK:
            if cls._FLUSHING:
                return
            cls._FLUSHING = True
        try:
            total, _ = cls.flush_offline_buffer(subject_prefix="[SMS OFFLINE][AUTO]")
            logger.info("sms.offline_autoflush_done", total=total)
        except Exception as e:  # pragma: no cover
            logger.error("sms.offline_autoflush_failed", err=str(e))
        finally:
            cls._LAST_FLUSH_TS = time.time()
            cls._FLUSHING = False

    # ──────────────────────────────────────────────────────────
    # Helpers de loteamento
    # ──────────────────────────────────────────────────────────
    @classmethod
    def _chunk_rows_into_files(cls, rows: list[tuple[str, str, str]], ts_master: str) -> list[_BuiltXLSX]:
        """
        Converte as linhas em vários arquivos XLSX, cada qual obedecendo:
          - no máx. _FILE_MAX_ROWS linhas
          - no máx. _FILE_MAX_BYTES bytes

        Retorna lista de _BuiltXLSX.
        """
        files: list[_BuiltXLSX] = []

        # fatia bruta por limite de linhas; refinamos por tamanho
        for i in range(0, len(rows), cls._FILE_MAX_ROWS):
            chunk = rows[i : i + cls._FILE_MAX_ROWS]
            # agora garantimos que o tamanho em bytes não estoura
            chunks_fit = cls._split_chunk_by_size(chunk, ts_master)
            files.extend(chunks_fit)

        return files

    @classmethod
    def _split_chunk_by_size(cls, chunk: list[tuple[str, str, str]], ts_master: str) -> list[_BuiltXLSX]:
        """
        Recebe um chunk (limitado por linhas) e, se o XLSX ficar maior que _FILE_MAX_BYTES,
        divide recursivamente até todos os arquivos caberem no limite.
        """
        result: list[_BuiltXLSX] = []
        # Tenta criar um arquivo com o chunk inteiro
        built = cls._build_xlsx_bytes(chunk, ts_master, index=1)
        if len(built.blob) <= cls._FILE_MAX_BYTES:
            result.append(built)
            return result

        # Se excedeu, divide em dois sub-chunks e trata recursivamente (divisão e conquista)
        mid = max(1, len(chunk) // 2)
        left = chunk[:mid]
        right = chunk[mid:]

        result.extend(cls._split_chunk_by_size(left, ts_master))
        result.extend(cls._split_chunk_by_size(right, ts_master))

        return result

    @staticmethod
    def _write_rows_to_ws(ws, rows: Iterable[tuple[str, str, str]]) -> int:
        ws.title = "sms_pendentes"
        ws.append(["timestamp_utc", "phone", "message"])
        count = 0
        for (t, phone, msg) in rows:
            ws.append([t, phone, msg])
            count += 1
        return count

    @classmethod
    def _build_xlsx_bytes(cls, rows: list[tuple[str, str, str]], ts_master: str, index: int) -> _BuiltXLSX:
        """
        Constrói um XLSX em memória e retorna metadados completos (_BuiltXLSX).
        """
        wb = Workbook()
        ws = wb.active
        count = cls._write_rows_to_ws(ws, rows)

        # grava em arquivo temporário (ficará para auditoria)
        with tempfile.NamedTemporaryFile(prefix=f"sms_offline_{ts_master}_", suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
            wb.save(tmp_path)

        # bytes para e-mail (Graph usa base64)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        file_bytes = buf.read()

        file_name = os.path.basename(tmp_path)
        logger.debug("sms.offline_file_built", file=file_name, rows=count, bytes=len(file_bytes), path=tmp_path)
        return _BuiltXLSX(name=file_name, blob=file_bytes, rows=count, path=tmp_path)

    @classmethod
    def _send_files_in_batched_emails(
        cls,
        files: list[_BuiltXLSX],
        subject_prefix: str,
        ts_master: str,
        total_rows: int,
    ) -> tuple[int, str | None]:
        """
        Agrupa anexos em e-mails respeitando:
          - _EMAIL_MAX_ATTACH anexos por e-mail
          - _EMAIL_MAX_BYTES bytes somados dos anexos por e-mail

        Retorna (emails_enviados, sample_path_or_None)
        """
        reporter = cls._OFFLINE_REPORTER
        if not reporter:
            logger.error("sms.offline_reporter_missing")
            return 0, None

        emails_sent = 0
        batch_attachments: list[dict] = []
        batch_bytes = 0
        batch_rows = 0
        email_idx = 1
        sample_path = files[0].path if files else None

        def flush_email_batch():
            nonlocal emails_sent, batch_attachments, batch_bytes, batch_rows, email_idx
            if not batch_attachments:
                return
            subject = f"{subject_prefix} {total_rows} mensagens pendentes — {ts_master} (lote {email_idx})"
            html = (
                f"<p>Relatório de SMS offline (lote <b>{email_idx}</b>) gerado em {ts_master}.</p>"
                f"<p>Total deste e-mail: <b>{batch_rows}</b> linhas, <b>{len(batch_attachments)}</b> anexo(s).</p>"
                f"<p>Total do ciclo: <b>{total_rows}</b> linhas.</p>"
                "<p>Colunas: <code>timestamp_utc, phone, message</code>.</p>"
            )
            try:
                reporter(subject, html, batch_attachments)
                emails_sent += 1
                logger.info(
                    "sms.offline_email_batch_sent",
                    email_index=email_idx,
                    attachments=len(batch_attachments),
                    batch_bytes=batch_bytes,
                    batch_rows=batch_rows,
                )
            except Exception as e:  # pragma: no cover
                logger.error("sms.offline_email_batch_failed", email_index=email_idx, err=str(e))
            finally:
                email_idx += 1
                batch_attachments.clear()
                batch_bytes = 0
                batch_rows = 0

        for built in files:
            one_attach = cls._to_graph_attachment(built.name, built.blob)
            one_size = len(built.blob)

            over_attach_count = len(batch_attachments) + 1 > cls._EMAIL_MAX_ATTACH
            over_bytes = (batch_bytes + one_size) > cls._EMAIL_MAX_BYTES

            if batch_attachments and (over_attach_count or over_bytes):
                flush_email_batch()

            batch_attachments.append(one_attach)
            batch_bytes += one_size
            batch_rows += built.rows

            if len(batch_attachments) >= cls._EMAIL_MAX_ATTACH or batch_bytes >= cls._EMAIL_MAX_BYTES:
                flush_email_batch()

        # Envia o que restou
        flush_email_batch()

        return emails_sent, sample_path

    @staticmethod
    def _to_graph_attachment(file_name: str, file_bytes: bytes) -> dict:
        """
        Converte bytes em anexo Microsoft Graph (base64).
        """
        return {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": file_name,
            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "contentBytes": base64.b64encode(file_bytes).decode("ascii"),
        }
