from __future__ import annotations

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.clinic_data_entity import ClinicDataEntity
from oralsin_core.core.domain.repositories.address_repository import AddressRepository
from oralsin_core.core.domain.repositories.clinic_data_repository import (
    ClinicDataRepository,
)
from plugins.django_interface.models import ClinicData as ClinicDataModel


class ClinicDataRepoImpl(ClinicDataRepository):
    def __init__(self, address_repo: AddressRepository):
        self._address_repo = address_repo

    # ─────────────────────────────── find ──────────────────────────────
    def find_by_id(self, data_id: str) -> ClinicDataEntity | None:
        try:
            return ClinicDataEntity.from_model(
                ClinicDataModel.objects.get(id=data_id)
            )
        except ClinicDataModel.DoesNotExist:
            return None

    def find_by_clinic(self, clinic_id: str) -> ClinicDataEntity | None:
        try:
            return ClinicDataEntity.from_model(
                ClinicDataModel.objects.get(clinic_id=clinic_id)
            )
        except ClinicDataModel.DoesNotExist:
            return None

    def list_by_clinic(self, clinic_id: str) -> list[ClinicDataEntity]:
        return [
            ClinicDataEntity.from_model(m)
            for m in ClinicDataModel.objects.filter(clinic_id=clinic_id)
        ]

    # ─────────────────────────────── save ──────────────────────────────
    def save(self, data: ClinicDataEntity) -> ClinicDataEntity:
        """
        Upsert de ClinicData: grava primeiro o Address (se existir)
        e depois referencia corretamente o address_id.
        """
        # 1) persistir o endereço aninhado
        if data.address:
            saved_addr = self._address_repo.save(data.address)
            data.address = saved_addr

        # 2) preparar defaults para o update_or_create
        real_cols = {f.attname for f in ClinicDataModel._meta.get_fields()}
        raw = data.to_dict()

        DROP_FIELDS = {"id", "address", "created_at", "updated_at"}
        defaults = {
            k: v
            for k, v in raw.items()
            if k in real_cols
            and k not in DROP_FIELDS
            and v is not None     
        }
        if data.address:
            defaults["address_id"] = data.address.id

        model, _ = ClinicDataModel.objects.update_or_create(
            clinic_id=data.clinic_id,  
            defaults=defaults,
        )
        return ClinicDataEntity.from_model(model)

    # ───────────────────────────── delete ──────────────────────────────
    def delete(self, clinic_data_id: str) -> None:
        ClinicDataModel.objects.filter(id=clinic_data_id).delete()

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[ClinicDataEntity]:
        """
        Retorna PagedResult contendo lista de ClinicDataEntity e total,
        aplicando paginação sobre ClinicDataModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = ClinicDataModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        clinica_data_page = qs.order_by('id')[offset: offset + page_size]

        items = [ClinicDataEntity.from_model(m) for m in clinica_data_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)