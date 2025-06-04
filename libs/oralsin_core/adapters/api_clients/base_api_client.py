from __future__ import annotations

from typing import Any, TypeVar
from urllib.parse import urljoin

import requests
import structlog
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

T = TypeVar("T", bound=BaseModel)


class BaseAPIClient:
    """
    Utilitário HTTP simples (GET) com:
      • retry exponencial
      • timeout configurável
      • parse + validação Pydantic
    """

    def __init__(
        self,
        *,
        base_url: str,
        default_headers: dict[str, str] | None = None,
        timeout: float = 5.0,
        retries: int = 3,
    ) -> None:
        self.log = structlog.get_logger(__name__).bind(component="BaseAPIClient")
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout

        self.log.debug("Configurando cliente", base_url=self.base_url, timeout=timeout)

        # sessão + retry -----------------------------------------------------------------
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

        retry_cfg = Retry(
            total=retries,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_cfg)
        for scheme in ("https://", "http://"):
            self.session.mount(scheme, adapter)

    # ---------------------------------------------------------------------- utils -----
    @staticmethod
    def _sanitize_payload(payload: Any) -> Any:
        """
        Remove None em campos string e normaliza estruturas conhecidas
        """
        if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], list):
            for rec in payload["data"]:
                for k, v in rec.items():
                    if v is None:
                        rec[k] = ""
        return payload

    # ---------------------------------------------------------------------- HTTP GET --
    def _get(self, path: str, *, params: dict[str, Any], response_model: type[T]) -> T:
        """
        Executa GET e retorna objeto Pydantic já validado.
        `path` pode conter chaves .format() – ex.: '/clinica/{id}'
        """
        url = urljoin(self.base_url, path.format(**params).lstrip("/"))
        log = self.log.bind(method="GET", url=url, params=params, model=response_model.__name__)
        log.debug("Enviando requisição")

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            log.debug("Resposta recebida", status_code=resp.status_code, headers=resp.headers)
            resp.raise_for_status()

            payload = self._sanitize_payload(resp.json())
            log.debug("Payload sanitizado", payload=payload)
            result = response_model.model_validate(payload)
            log.info("Resposta validada com sucesso")
            return result

        except Exception as exc:  # noqa: BLE001
            log.error("Falha em _get()", error=str(exc), exc_info=True)
            raise
