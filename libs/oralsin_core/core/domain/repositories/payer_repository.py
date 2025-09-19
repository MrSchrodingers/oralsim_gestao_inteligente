from __future__ import annotations
from abc import ABC, abstractmethod
import uuid
from oralsin_core.core.domain.entities.payer_entity import PayerEntity

class PayerRepository(ABC):
    @abstractmethod
    def upsert(self, payer: PayerEntity) -> PayerEntity:
        """Cria ou atualiza um pagador e seus telefones no banco de dados."""
        ...

    @abstractmethod
    def find_by_patient_id(self, patient_id: uuid.UUID) -> list[PayerEntity]:
        """Encontra todos os pagadores associados a um paciente."""
        ...