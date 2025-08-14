from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin
from oralsin_core.core.domain.entities.address_entity import AddressEntity
from oralsin_core.core.domain.entities.patient_phone_entity import PatientPhoneEntity


@dataclass(slots=True)
class PatientEntity(EntityMixin):
    id: uuid.UUID
    oralsin_patient_id: int | None
    clinic_id: uuid.UUID
    name: str
    cpf: str | None = None
    address: AddressEntity | None = None
    contact_name: str | None = None
    email: str | None = None
    flow_type: str | None = None
    phones: list[PatientPhoneEntity] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def masked_cpf(self) -> str | None:
        if not self.cpf or len(self.cpf) < 3:  # noqa: PLR2004
            return None
        return f"***.***.***-{self.cpf[-2:]}"
    
    def to_dict(self) -> dict[str, any]:
        data = {
            "oralsin_patient_id": self.oralsin_patient_id,
            "clinic_id": str(self.clinic_id),
            "name": self.name,
            "cpf": self.cpf,
            "flow_type": self.flow_type,
            "contact_name": self.contact_name,
            "email": self.email,
        }
        if self.address:
            data["address"] = {
                "id": str(self.address.id),
                "street": self.address.street,
                "number": self.address.number,
                "complement": self.address.complement,
                "neighborhood": self.address.neighborhood,
                "city": self.address.city,
                "state": self.address.state,
                "zip_code": self.address.zip_code,
            }
        if self.phones:
            data["phones"] = [phone.to_dict() for phone in self.phones]
        return data
