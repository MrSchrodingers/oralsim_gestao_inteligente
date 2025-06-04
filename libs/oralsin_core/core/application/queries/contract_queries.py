from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO


@dataclass(frozen=True)
class ListContractsQuery(QueryDTO):
    """
    Query para listar contratos, com filtros embutidos em `params`.
    """
    name: str = "ListContractsQuery"
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True)
class GetContractQuery(QueryDTO):
    """
    Query para recuperar detalhes de um contrato por ID.
    """
    contract_id: str
