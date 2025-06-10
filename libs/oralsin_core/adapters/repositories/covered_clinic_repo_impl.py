from __future__ import annotations

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.covered_clinics import CoveredClinicEntity
from oralsin_core.core.domain.repositories.covered_clinic_repository import (
    CoveredClinicRepository,
)
from plugins.django_interface.models import (
    Clinic as ClinicModel,
)
from plugins.django_interface.models import (
    CoveredClinic as CoveredClinicModel,
)


class CoveredClinicRepoImpl(CoveredClinicRepository):
    # ───────────────────────────────────────────────
    # Consultas
    # ───────────────────────────────────────────────
    def find_by_id(self, covered_id: str) -> CoveredClinicEntity | None:
        try:
            m = CoveredClinicModel.objects.get(id=covered_id)
            return CoveredClinicEntity.from_model(m)
        except CoveredClinicModel.DoesNotExist:
            return None

    def find_by_api_id(self, oralsin_id: int) -> CoveredClinicEntity | None:
        try:
            m = CoveredClinicModel.objects.get(oralsin_clinic_id=oralsin_id)
            return CoveredClinicEntity.from_model(m)
        except CoveredClinicModel.DoesNotExist:
            return None

    def list_all(self) -> list[CoveredClinicEntity]:
        return [
            CoveredClinicEntity.from_model(m)
            for m in CoveredClinicModel.objects.all()
        ]

    # ───────────────────────────────────────────────
    # Persistência (Upsert)
    # ───────────────────────────────────────────────
    def save(self, entity: CoveredClinicEntity) -> CoveredClinicEntity:
        """
        Garante que:
        1. Exista um `Clinic` local com o mesmo `oralsin_clinic_id`.
        2. Salve/atualize `CoveredClinic` apontando para essa clínica.
        """
        # 1️⃣  Resolve (ou cria) a própria Clinic
        clinic_obj, _ = ClinicModel.objects.get_or_create(
            oralsin_clinic_id=entity.oralsin_clinic_id,
            defaults={
                "name": entity.name or "Clínica sem nome",
                "cnpj": entity.cnpj,
            },
        )

        # 2️⃣  Monta campos defaults / update
        defaults = {
            "clinic": clinic_obj,
            "name": entity.name,
            "corporate_name": entity.corporate_name,
            "acronym": entity.acronym,
            "cnpj": entity.cnpj,
            "active": entity.active,
        }

        model, _ = CoveredClinicModel.objects.update_or_create(
            oralsin_clinic_id=entity.oralsin_clinic_id,
            defaults=defaults,
        )
        return CoveredClinicEntity.from_model(model)

    # ───────────────────────────────────────────────
    # Remoção
    # ───────────────────────────────────────────────
    def delete(self, covered_id: str) -> None:
        CoveredClinicModel.objects.filter(id=covered_id).delete()    
    
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[CoveredClinicEntity]:
        """
        Retorna PagedResult contendo lista de CoveredClinicEntity e total,
        aplicando paginação sobre CoveredClinicModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = CoveredClinicModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        clinicas_covered_page = qs.order_by('id')[offset: offset + page_size]

        items = [CoveredClinicEntity.from_model(m) for m in clinicas_covered_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)