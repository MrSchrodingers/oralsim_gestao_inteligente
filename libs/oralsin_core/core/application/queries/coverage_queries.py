from __future__ import annotations

from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListCoveredClinicsQuery(QueryDTO[None]):
    filtros: None = None

@dataclass(frozen=True)
class ListUserClinicsQuery(QueryDTO[dict]):
    filtros: dict  # {'user_id': str}