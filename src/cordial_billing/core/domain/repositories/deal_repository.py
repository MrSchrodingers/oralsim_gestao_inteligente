from abc import ABC, abstractmethod

from cordial_billing.core.domain.entities.pipedrive_deal_entity import PipedriveDealEntity


class DealRepository(ABC):
    @abstractmethod
    def find_by_cpf(self, cpf: str) -> PipedriveDealEntity | None:
      """
      Busca um negócio pelo CPF.
      """
      ...
