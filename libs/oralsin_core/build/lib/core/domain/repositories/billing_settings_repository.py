from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.billing_settings_entity import BillingSettingsEntity


class BillingSettingsRepository(ABC):
    @abstractmethod
    def get(self, clinic_id: str) -> BillingSettingsEntity | None:
        ...

    @abstractmethod
    def update(self, settings: BillingSettingsEntity) -> BillingSettingsEntity:
        ...
        
    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[BillingSettingsEntity]:
        """
        Retorna PagedResult contendo lista da Entidade e total,
        aplicando paginação sobre o Modelo.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        ...