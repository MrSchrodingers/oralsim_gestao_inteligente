from __future__ import annotations

from collections.abc import Sequence

import structlog

from config import settings
from oralsin_core.adapters.api_clients.base_api_client import BaseAPIClient
from oralsin_core.core.application.cqrs import PagedResult, PaginatedQueryDTO
from oralsin_core.core.application.dtos.oralsin_dtos import (
    ClinicaSearchResponseDTO,
    ClinicsQueryDTO,
    ContratoDetalheQueryDTO,
    InadimplenciaContratoResponseDTO,
    InadimplenciaQueryDTO,
    InadimplenciaResponseDTO,
    OralsinClinicDTO,
    OralsinContratoDetalhadoDTO,
    OralsinPacienteDTO,
)

logger = structlog.get_logger(__name__)


class OralsinAPIClient(BaseAPIClient):
    """
    Wrapper de alto-nível para a API Oralsin.
    Permite buscar clínica por **nome** (search) ou por **id**,
    e expõe helpers para inadimplência/contratos.
    """

    # ---------------------------------------------------------------- init ----------
    def __init__(self) -> None:
        super().__init__(
            base_url=settings.ORALSIN_API_BASE,
            default_headers={"Accept": "application/json"},
            timeout=settings.ORALSIN_TIMEOUT,
        )
        # token vai em TODOS os requests
        self.session.params.update({"api_token": settings.ORALSIN_API_TOKEN})
        logger.debug("OralsinAPIClient inicializado", base_url=self.base_url)

    # ---------------------------------------------------------------- clinics -------
    def _fetch_paginated(
        self,
        *,
        endpoint: str,
        query: PaginatedQueryDTO,
        response_model: type[ClinicaSearchResponseDTO],
    ) -> PagedResult[OralsinClinicDTO]:
        """Helper interno de paginação."""
        params = {
            **query.filtros.dict(by_alias=True, exclude_none=True),
            "page": query.page,
            "per_page": query.page_size,
        }
        raw = self._get(endpoint, params=params, response_model=response_model)
        items = [OralsinClinicDTO.model_validate(item) for item in raw.data]
        return PagedResult(
            items=items,
            total=raw.total,
            page=raw.current_page,
            page_size=raw.per_page,
        )

    # -------- detalhe por id --------------------------------------------------------
    def get_clinic_by_id(self, oralsin_id: int) -> OralsinClinicDTO:
        """
        Chama `/clinica/{id}` (endpoint de detalhe).  
        Útil quando já temos o idClinica.
        """
        return self._get(
            f"/clinica/{oralsin_id}",
            params={},                       # já está no path
            response_model=OralsinClinicDTO,
        )

    # -------- lista / busca ---------------------------------------------------------
    def get_clinics(
        self, query: PaginatedQueryDTO[ClinicsQueryDTO]
    ) -> PagedResult[OralsinClinicDTO]:
        """
        • Se `idClinica` vier no filtro ⇒ devolve exatamente **1** item  
        • Caso contrário ⇒ usa busca paginada (`search=<nome>` etc.)
        """
        if query.filtros.idClinica:
            clinic = self.get_clinic_by_id(query.filtros.idClinica)
            return PagedResult(items=[clinic], total=1, page=1, page_size=1)

        return self._fetch_paginated(
            endpoint="/clinica",
            query=query,
            response_model=ClinicaSearchResponseDTO,
        )

    # ----------------------------------------------------------- inadimplência ------
    def get_inadimplencia(
        self, query: InadimplenciaQueryDTO
    ) -> Sequence[OralsinPacienteDTO]:
        params = query.dict(by_alias=True, exclude_none=True)
        raw = self._get(
            "/relatorio/inadimplencia",
            params=params,
            response_model=InadimplenciaResponseDTO,
        )
        return [OralsinPacienteDTO.model_validate(item) for item in raw.data]

    # --------------------------------------------------------------- contrato -------
    def get_contract_details(
        self, query: ContratoDetalheQueryDTO
    ) -> OralsinContratoDetalhadoDTO:
        params = query.dict(by_alias=True, exclude_none=True)
        raw = self._get(
            "/relatorio/inadimplencia/contrato",
            params=params,
            response_model=InadimplenciaContratoResponseDTO,
        )
        return raw.data
