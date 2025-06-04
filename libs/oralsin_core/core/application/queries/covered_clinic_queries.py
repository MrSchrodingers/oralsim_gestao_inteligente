from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListCoveredClinicsQuery(QueryDTO):
    """
    Query para listar clínicas cobertas registradas.
    """
    name: str = "ListCoveredClinicsQuery"
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True)
class GetCoveredClinicQuery(QueryDTO):
    """
    Query para recuperar uma clínica coberta por seu ID interno.
    """
    clinic_id: str