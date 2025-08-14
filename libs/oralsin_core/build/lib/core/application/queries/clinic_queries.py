from dataclasses import dataclass

from oralsin_core.core.application.cqrs import PaginatedQueryDTO


@dataclass(frozen=True)
class GetClinicQuery:
    id: str

class ListClinicsQuery(PaginatedQueryDTO[dict]):
    """
    Query paginada para listar clínicas.
    `filtros` pode conter chaves como 'name' ou 'cnpj'.
    """
    pass
