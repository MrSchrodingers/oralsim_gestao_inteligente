from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from oralsin_core.core.domain.entities._base import EntityMixin
from plugins.django_interface.models import CoveredClinic as CoveredClinicModel


@dataclass(slots=True)
class CoveredClinicEntity(EntityMixin):
    id: uuid.UUID
    oralsin_clinic_id: int
    clinic_id: uuid.UUID
    name: str
    cnpj: str | None = None
    corporate_name: str | None = None
    acronym: str | None = None
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_active_str(self) -> str:
        return "Ativa" if self.active else "Inativa"    
    
    @classmethod
    def from_model(cls, model: CoveredClinicModel) -> CoveredClinicEntity:
        """
        Constrói a entidade a partir de um Django CoveredClinic instance,
        extraindo clinic_id e espelhando todos os campos relevantes.
        """
        return cls(
            id=model.id,
            clinic_id=model.clinic_id,
            oralsin_clinic_id=model.oralsin_clinic_id,
            name=model.name,
            cnpj=model.cnpj,
            corporate_name=model.corporate_name,
            acronym=model.acronym,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )