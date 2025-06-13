from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.payment_method_entity import PaymentMethodEntity


class PaymentMethodRepository(ABC):
    @abstractmethod
    def find_by_id(self, payment_method_id: str) -> PaymentMethodEntity | None:
        """Retorna um métodos de pagamento pelo ID interno."""
        ...

    @abstractmethod
    def find_by_oralsin_method_id(self, oralsin_method_id: str) -> list[PaymentMethodEntity]:
        """Lista métodos de pagamento pelo ID externo."""
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[PaymentMethodEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...