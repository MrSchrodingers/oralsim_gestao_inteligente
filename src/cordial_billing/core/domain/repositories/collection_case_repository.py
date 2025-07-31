from abc import ABC, abstractmethod
from typing import Any

from oralsin_core.core.application.cqrs import PagedResult

from cordial_billing.core.domain.entities.collection_case_entity import (
    CollectionCaseEntity,
)


class CollectionCaseRepository(ABC):
    @abstractmethod
    def find_by_installment_id(self, installment_id: str) -> CollectionCaseEntity | None:
        ...
        
    @abstractmethod
    def find_by_id(self, collection_case_id: str) -> CollectionCaseEntity | None:
        ...
    @abstractmethod
    def save(self, case: CollectionCaseEntity) -> CollectionCaseEntity: ...

    @abstractmethod
    def get_summary_by_clinic(self, clinic_id: str) -> dict[str, Any]:
        ...
        
    @abstractmethod
    def exists_for_installment(self, installment_id: str) -> bool: ...

    @abstractmethod
    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[CollectionCaseEntity]:
        ...