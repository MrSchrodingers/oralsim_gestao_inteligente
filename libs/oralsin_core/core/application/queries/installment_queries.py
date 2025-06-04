from dataclasses import dataclass

from oralsin_core.core.application.cqrs import QueryDTO
from oralsin_core.core.application.dtos.contract_dto import ContractQueryDTO


@dataclass(frozen=True, slots=True)
class ListInstallmentsQuery(QueryDTO):
    """
    Query para listar parcelas de um contrato, com paginação.
    - payload: ContractQueryDTO contendo contract_id e opcionais (datas, status, etc.).
    - page: número da página (default=1)
    - page_size: tamanho da página (default=50)
    """
    payload: ContractQueryDTO
    page: int = 1
    page_size: int = 50

@dataclass(frozen=True, slots=True)
class GetInstallmentQuery(QueryDTO):
    id: str