from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from .address_entity import AddressEntity
from .patient_entity import PatientEntity


@dataclass
class PayerPhoneEntity:
    """Entidade que representa o telefone de um pagante."""
    id: uuid.UUID
    payer_id: uuid.UUID
    phone_number: str
    phone_type: str | None = None

@dataclass
class PayerEntity:
    """Entidade que representa o pagante de uma parcela ou contrato."""
    id: uuid.UUID
    patient_id: uuid.UUID  # Vínculo com o paciente original
    name: str
    document: Optional[str] = None
    document_type: Optional[str] = None
    relationship: Optional[str] = None # Grau de parentesco
    is_patient_the_payer: bool = True # Flag de otimização
    address: Optional[AddressEntity] = None
    email: Optional[str] = None
    phones: List[PayerPhoneEntity] = field(default_factory=list)

    @classmethod
    def from_patient(cls, patient: PatientEntity) -> PayerEntity:
        """Cria uma entidade Payer a partir de uma entidade Patient."""
        payer_id = uuid.uuid4()
        # Copia telefones do paciente para o pagante
        payer_phones = [
            PayerPhoneEntity(
                id=uuid.uuid4(),
                payer_id=payer_id,
                phone_number=phone.phone_number,
                phone_type=phone.phone_type,
            )
            for phone in patient.phones.all()
        ]
        return cls(
            id=payer_id,
            patient_id=patient.id,
            name=patient.name,
            document=patient.cpf,
            document_type="CPF" if patient.cpf else None,
            is_patient_the_payer=True,
            address=patient.address,
            email=patient.email,
            phones=payer_phones,
        )