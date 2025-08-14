from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class AddressEntity(EntityMixin):
    id: uuid.UUID
    street: str
    number: str
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    @property
    def formatted_zip_code(self) -> str:
        """
        Formata o CEP para o padrão XXXXX-XXX se ele for um CEP válido de 8 dígitos.
        """
        if self.zip_code and len(self.zip_code) == 8 and self.zip_code.isdigit():  # noqa: PLR2004
            return f"{self.zip_code[:5]}-{self.zip_code[5:]}"
        return self.zip_code or ""
    
    def __str__(self) -> str:
        """Retorna o endereço formatado como uma string legível."""
        parts = [
            f"{self.street}, {self.number}" if self.number else self.street,
            self.complement,
            self.neighborhood,
            f"{self.city}/{self.state}",
            f"CEP {self.formatted_zip_code}" if self.zip_code else None,
        ]
        return " - ".join(p for p in parts if p)
    
    @classmethod
    def from_dict(cls, data: dict) -> AddressEntity:
        raw_id = data.get("id")
        if isinstance(raw_id, uuid.UUID):
            id_ = raw_id
        elif isinstance(raw_id, str):
            id_ = uuid.UUID(raw_id)
        else:
            id_ = uuid.uuid4()

        return cls(
            id=id_,
            street=data["street"],
            number=data["number"],
            complement=data.get("complement"),
            neighborhood=data.get("neighborhood"),
            city=data.get("city"),
            state=data.get("state"),
            zip_code=data.get("zip_code"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
