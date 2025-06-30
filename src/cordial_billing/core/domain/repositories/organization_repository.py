from abc import ABC, abstractmethod


class OrganizationRepository(ABC):
    @abstractmethod
    async def find_id_by_cnpj(self, cnpj: str) -> int | None: ...
