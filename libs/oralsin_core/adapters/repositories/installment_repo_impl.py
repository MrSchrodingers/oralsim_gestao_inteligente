from datetime import date, timedelta
from typing import Any

from django.db import IntegrityError, transaction

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from plugins.django_interface.models import Installment as InstallmentModel


class InstallmentRepoImpl(InstallmentRepository):
    def __init__(self, mapper: OralsinPayloadMapper):
        self.mapper = mapper
    # ─────────────────── consultas de parcelas em atraso ───────────────────
    def _overdue(  # noqa: PLR0913
        self,
        contract_id: str,
        min_days_overdue: int,
        offset: int,
        limit: int,
        is_current: bool = False,
        *,
        contract_version: int | None = None,
    ) -> PagedResult[InstallmentEntity]:
        filters = dict(
            contract_id=contract_id,
            received=False,
            due_date__lt=date.today() - timedelta(days=min_days_overdue),
            is_current=is_current,
        )
        if contract_version is not None:
            filters["contract_version"] = contract_version

        qs = InstallmentModel.objects.filter(**filters).order_by("due_date")
        total = qs.count()
        items = [InstallmentEntity.from_model(m) for m in qs[offset : offset + limit]]
        return PagedResult(
            items=items, total=total, page=(offset // limit) + 1, page_size=limit
        )

    def find_by_id(self, installment_id: str) -> InstallmentEntity | None:
        try:
            m = InstallmentModel.objects.get(id=installment_id)
            return InstallmentEntity.from_model(m)
        except InstallmentModel.DoesNotExist:
            return None

    def has_overdue(
        self,
        contract_id: str,
        min_days_overdue: int,
        *,
        contract_version: int | None = None,
    ) -> bool:
        return (
            self._overdue(contract_id, min_days_overdue, 0, 1, contract_version=contract_version).total
            > 0
        )

    def list_overdue(
        self,
        contract_id: str,
        min_days_overdue: int,
        offset: int,
        limit: int,
        *,
        contract_version: int | None = None,
    ) -> PagedResult[InstallmentEntity]:
        return self._overdue(
            contract_id, min_days_overdue, offset, limit, contract_version=contract_version
        )
        
    def list_current_overdue(
        self,
        contract_id: str,
        min_days_overdue: int,
        offset: int,
        limit: int,
        *,
        contract_version: int | None = None,
    ) -> PagedResult[InstallmentEntity]:
        return self._overdue(
            contract_id, min_days_overdue, offset, limit, contract_version=contract_version, is_current=True
        )

    # ─────────────────────────── persistência ────────────────────────────
    @transaction.atomic
    def merge_installments(self, parcelas: list, parcela_atual: Any | None, contract_id: str):
        """
        Retorna uma lista de InstallmentEntity única, priorizando parcelaAtualDetalhe.
        """
        parcel_map = {}
        # 1. Mapeia todas as parcelas normais
        for ent in self.mapper.map_installments(parcelas, None, contract_id):
            key = (ent.contract_id, ent.contract_version, ent.installment_number)
            parcel_map[key] = ent
        # 2. Se existir parcela_atual, sobrescreve (garantindo sempre que tem numeroParcela certo)
        if parcela_atual:
            ent = self.mapper.map_installment(parcela_atual, contract_id, parcelas) 
            key = (ent.contract_id, ent.contract_version, ent.installment_number)
            parcel_map[key] = ent
        return list(parcel_map.values())

    @transaction.atomic
    def save(self, inst: InstallmentEntity) -> InstallmentEntity:
        natural_key = dict(
            contract_id=inst.contract_id,
            contract_version=inst.contract_version,
            installment_number=inst.installment_number,
        )
        defaults = {
            "id": inst.id,
            "oralsin_installment_id": inst.oralsin_installment_id,
            "due_date": inst.due_date,
            "installment_amount": inst.installment_amount,
            "received": inst.received,
            "installment_status": inst.installment_status,
            "payment_method_id": (
                inst.payment_method.id if inst.payment_method else None
            ),
            "is_current": inst.is_current,
        }

        try:
            model, created = InstallmentModel.objects.update_or_create(
                **natural_key,
                defaults=defaults,
            )
        except IntegrityError:
            # fallback para concorrência: só atualiza os demais campos, sem mexer no PK
            model = InstallmentModel.objects.get(**natural_key)
            for field, value in defaults.items():
                if field != "id":
                    setattr(model, field, value)
            model.save(update_fields=[f for f in defaults if f != "id"])

        # garante que só uma parcela está marcada como current
        if inst.is_current:
            (
                InstallmentModel.objects
                .filter(
                    contract_id=inst.contract_id,
                    contract_version=inst.contract_version,
                )
                .exclude(installment_number=inst.installment_number)
                .update(is_current=False)
            )

        return InstallmentEntity.from_model(model)

    def get_trigger_installment(self, contract_id: str) -> InstallmentEntity | None:
        try:
            m = InstallmentModel.objects.get(contract_id=contract_id, is_current=True)
            return InstallmentEntity.from_model(m)
        except InstallmentModel.DoesNotExist:
            return None

    def get_current_installment(self, contract_id: str) -> InstallmentEntity | None:
        try:
            m = InstallmentModel.objects.get(contract_id=contract_id, is_current=True)
            return InstallmentEntity.from_model(m)
        except InstallmentModel.DoesNotExist:
            return None
    
    def delete(self, installment_id: str) -> None:
        InstallmentModel.objects.filter(id=installment_id).delete()
