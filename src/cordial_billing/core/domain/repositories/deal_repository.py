from abc import ABC, abstractmethod

from cordial_billing.core.domain.entities.pipedrive_deal_entity import PipedriveDealEntity


class DealRepository(ABC):
    @abstractmethod
    def find_by_cpf(self, cpf: str) -> PipedriveDealEntity | None:
      """
      Busca um negócio pelo CPF.
      """
      ...

    @abstractmethod
    async def find_by_id(self, deal_id: int) -> PipedriveDealEntity | None:
      """
      Busca um negócio pelo deal_id.
      """
      ...
    
    @abstractmethod
    async def find_cpf_by_deal_id(self, deal_id: int) -> str | None:
      """
      Busca um CPF pelo deal_id da relação pessoa.negocio_id = negocio.id.
      """
      ...