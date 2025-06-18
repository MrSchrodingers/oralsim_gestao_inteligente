from __future__ import annotations

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.clinic_entity import ClinicEntity
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from plugins.django_interface.models import Clinic as ClinicModel


class ClinicRepoImpl(ClinicRepository):
    # ───────────────────────────────────────────────
    # Queries
    # ───────────────────────────────────────────────
    def find_by_id(self, clinic_id: str) -> ClinicEntity | None:
        try:
            return ClinicEntity.from_model(ClinicModel.objects.get(id=clinic_id))
        except ClinicModel.DoesNotExist:
            return None
        
    def find_by_oralsin_id(self, oralsin_id: int) -> ClinicEntity | None:
        try:
            return ClinicEntity.from_model(
                ClinicModel.objects.get(oralsin_clinic_id=oralsin_id)
            )
        except ClinicModel.DoesNotExist:
            return None

    def find_by_name(self, name: str) -> list[ClinicEntity]:
        qs = ClinicModel.objects.filter(name__icontains=name)
        return [ClinicEntity.from_model(m) for m in qs]

    # ───────────────────────────────────────────────
    # Helper usado pelo CoveredClinicRepo
    # ───────────────────────────────────────────────
    def get_or_create_by_oralsin_id(
        self,
        oralsin_clinic_id: int,
        *,
        name: str | None = None,
        cnpj: str | None = None,
    ) -> ClinicEntity:
        """
        Garante que exista um Clinic local para o `oralsin_clinic_id`.
        Se não existir, cria com nome/cnpj mínimos.
        """
        defaults = {"name": name or f"Clinic {oralsin_clinic_id}", "cnpj": cnpj}
        model, _ = ClinicModel.objects.get_or_create(
            oralsin_clinic_id=oralsin_clinic_id, defaults=defaults
        )
        return ClinicEntity.from_model(model)

    # ───────────────────────────────────────────────
    # Persistência padrão
    # ───────────────────────────────────────────────
    def save(self, clinic: ClinicEntity) -> ClinicEntity:
        model, _ = ClinicModel.objects.update_or_create(
            oralsin_clinic_id=clinic.oralsin_clinic_id,
            defaults={
                "name": clinic.name,
                "cnpj": clinic.cnpj,
            },
        )
        return ClinicEntity.from_model(model)

    def delete(self, clinic_id: str) -> None:
        ClinicModel.objects.filter(id=clinic_id).delete()

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[ClinicEntity]:
        """
        Retorna PagedResult contendo lista de ClinicEntity e total,
        aplicando paginação sobre ClinicModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = ClinicModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        clinica_page = qs.order_by('id')[offset: offset + page_size]

        items = [ClinicEntity.from_model(m) for m in clinica_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)