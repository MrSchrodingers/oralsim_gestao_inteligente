from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListPatientsQuery(QueryDTO):
    """
    Query paginada para listar pacientes, suportando filtros em `params`.
    """
    name: str = "ListPatientsQuery"
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True)
class GetPatientQuery(QueryDTO):
    """
    Query para recuperar um único paciente por ID.
    """
    patient_id: str