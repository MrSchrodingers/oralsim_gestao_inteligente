from __future__ import annotations

import json
from typing import Any

import requests
from oralsin_core.adapters.api_clients.base_api_client import BaseAPIClient

from config import settings


class PipedriveAPIClient(BaseAPIClient):
    def __init__(self) -> None:
        super().__init__(
            base_url=settings.PIPEDRIVE_API_BASE,    
            default_headers={"Accept": "application/json"},
            timeout=5.0,
        )
        if settings.PIPEDRIVE_API_TOKEN:
            self.session.params.update({"api_token": settings.PIPEDRIVE_API_TOKEN})

    # ─────────────────────────── util interno ──────────────────────────
    def _safe_request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Executa a request capturando exceções de rede e
        tentando sempre converter a resposta para JSON.
        """
        url = f"{self.base_url}{endpoint.lstrip('/')}"
        try:
            resp: requests.Response = self.session.request(
                method.upper(), url, params=params, json=json_body, timeout=self.timeout
            )
        except requests.RequestException as exc:
            return {
                "status_code": None,
                "ok": False,
                "headers": {},
                "json": None,
                "text": str(exc),
            }

        try:
            parsed = resp.json()
        except json.JSONDecodeError:
            parsed = None

        return {
            "status_code": resp.status_code,
            "ok": resp.ok,
            "headers": dict(resp.headers),
            "json": parsed,
            "text": resp.text,
        }

    # ─────────────────────────── Deals ──────────────────────────
    def create_deal(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._safe_request("post", "deals", json_body=payload)

    # ─────────────────────────── Persons ─────────────────────────
    def search_persons(self, *, term: str) -> dict[str, Any]:
        return self._safe_request("get", "persons/search", params={"term": term})

    def create_person(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._safe_request("post", "persons", json_body=payload)
