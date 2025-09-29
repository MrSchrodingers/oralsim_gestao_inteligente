from __future__ import annotations

from datetime import date
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from .address_entity import AddressEntity
from .patient_entity import PatientEntity

def normalize_phones(phones_field):
    if not phones_field:
        return []
    # Django RelatedManager/QuerySet
    if hasattr(phones_field, "all"):
        return list(phones_field.all())
    try:
        return list(phones_field)
    except TypeError:
        return []
    
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
    date_of_birth: date | None = None
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
        
        payer_phones = [
            PayerPhoneEntity(
                id=uuid.uuid4(),
                payer_id=payer_id,
                phone_number=ph.phone_number,
                phone_type=ph.phone_type,
            )
            for ph in normalize_phones(getattr(patient, "phones", None))
        ]
        return cls(
            id=payer_id,
            patient_id=patient.id,
            name=patient.name,
            date_of_birth=patient.date_of_birth,
            document=patient.cpf,
            document_type="CPF" if patient.cpf else None,
            is_patient_the_payer=True,
            address=patient.address,
            email=patient.email,
            phones=payer_phones,
        )