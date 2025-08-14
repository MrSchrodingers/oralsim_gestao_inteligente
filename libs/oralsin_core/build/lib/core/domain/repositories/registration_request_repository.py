import uuid
from abc import ABC, abstractmethod

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.registration_request_entity import RegistrationRequestEntity


class RegistrationRequestRepository(ABC):
    @abstractmethod
    def find_by_id(self, request_id: uuid.UUID) -> RegistrationRequestEntity | None:
        ...

    @abstractmethod
    def save(self, request: RegistrationRequestEntity) -> RegistrationRequestEntity:
        ...

    @abstractmethod
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[RegistrationRequestEntity]:
        ...