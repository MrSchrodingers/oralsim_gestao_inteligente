from abc import ABC, abstractmethod

from cordial_billing.core.domain.entities.collection_case_entity import (
    CollectionCaseEntity,
)


class CollectionCaseRepository(ABC):
    @abstractmethod
    def save(self, case: CollectionCaseEntity) -> CollectionCaseEntity: ...

    @abstractmethod
    def exists_for_installment(self, installment_id: str) -> bool: ...
