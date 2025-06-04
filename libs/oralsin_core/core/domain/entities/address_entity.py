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
