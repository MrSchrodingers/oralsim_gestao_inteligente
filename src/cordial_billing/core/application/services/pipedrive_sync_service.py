from __future__ import annotations

import re
from typing import Any

from structlog import get_logger

from cordial_billing.adapters.api_clients.pipedrive_api_client import (
    PipedriveAPIClient,
)
from cordial_billing.core.domain.repositories.organization_repository import (
    OrganizationRepository,
)

log = get_logger(__name__)


def _digits(text: str | None) -> str:
    """Mantém apenas os dígitos (útil p/ CPF e telefones)."""
    return re.sub(r"\D", "", text or "")


class PipedriveSyncService:
    """
    • Organizações (clinics) são buscadas no Pipeboard.  
    • Pessoas são buscadas/ criadas no Pipedrive antes de abrir o Deal.
    """

    CPF_CF: str = "1ba49a9ebfb25bd0a2f0d223ddc6d4b09e59b8c5"      # campo custom CPF
    ADDRESS_CF: str = "115dbb4bdb23137d44f9ffbcfe312126213371b3"   # campo custom Endereço
    DEFAULT_OWNER: int = 22346271                                   # usuário Cordial

    # -----------------------------------------------------------------
    def __init__(
        self,
        client: PipedriveAPIClient,
        org_repo: OrganizationRepository,
    ) -> None:
        self.client = client
        self._org_repo = org_repo

    # ─────────────────────────── ORG ────────────────────────────────
    async def ensure_org_id(self, *, cnpj: str) -> int:
        """Localiza o *org_id*; levanta erro se não achar."""
        if org_id := await self._org_repo.find_id_by_cnpj(cnpj):
            return org_id
        log.error("org_not_found", cnpj=cnpj)
        raise ValueError(f"Organização (CNPJ={cnpj}) não encontrada")

    # ───────────────────── helpers (phones & payload) ───────────────
    def _collect_phones(self, patient) -> list[str]:
        """Retorna lista de telefones (strings sem formatação)."""
        raw = [p.phone_number for p in patient.prefetched_phones] if hasattr(patient, "prefetched_phones") else list(patient.phones.values_list("phone_number", flat=True))
        return [_digits(ph) for ph in raw if ph]

    def _build_person_payload(
        self,
        *,
        patient,
        org_id: int,
        phones: list[str],
        cpf_raw: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name":       patient.name,
            "org_id":     org_id,
            "owner_id":   self.DEFAULT_OWNER,
            "visible_to": 3,        
            "custom_fields": {},
        }

        # --- custom fields -----------------------------------------
        if cpf_raw:
            payload["custom_fields"][self.CPF_CF] = cpf_raw

        if getattr(patient, "address", None):
            a = patient.address
            payload["custom_fields"][self.ADDRESS_CF] = (
                f"Logradouro: {a.street}, Nº: {a.number}, Bairro: {a.neighborhood}, "
                f"Cidade: {a.city}, Estado: {a.state}, CEP: {a.zip_code}"
            )

        # --- phones -------------------------------------------------
        if phones:
            payload["phones"] = [
                {"value": ph, "label": "work", "primary": idx == 0}
                for idx, ph in enumerate(phones)
            ]

        # --- e-mails -----------------------------------------------
        if patient.email:
            payload["emails"] = [{"value": patient.email, "label": "work"}]

        return payload

    # ─────────────────────── PERSON (pública) ──────────────────────
    def ensure_person(self, *, patient, org_id: int) -> int:
        """
        Garante que a *Person* exista no Pipedrive e devolve seu ID.
        Busca prioritariamente pelo CPF.
        """
        cpf_raw = _digits(
            getattr(patient, "cpf", "") or getattr(patient, "cpf_raw", "")
        )
        search = self.client.search_persons(term=cpf_raw or patient.name)

        if person_id := self._extract_first_id(search):
            return person_id

        # não achou → cria
        phones = self._collect_phones(patient)
        body   = self._build_person_payload(
            patient=patient,
            org_id=org_id,
            phones=phones,
            cpf_raw=cpf_raw,
        )
        created = self.client.create_person(body)

        if not created.get("ok"):
            log.error(
                "create_person_failed",
                org_id=org_id,
                status=created.get("status_code"),
                body=created.get("json") or created.get("text"),
            )
            raise ValueError("Falha ao criar Person no Pipedrive")

        person_id = created["json"]["data"]["id"]
        log.info("created_person", person_id=person_id, org_id=org_id)
        return person_id

    # -----------------------------------------------------------------
    @staticmethod
    def _extract_first_id(resp: dict | None) -> int | None:
        """Extrai o primeiro `id` de search_persons()."""
        items = (resp or {}).get("data", {}).get("items", [])
        return items[0]["item"]["id"] if items else None
