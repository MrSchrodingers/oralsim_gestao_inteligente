from __future__ import annotations

import uuid
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from oralsin_core.adapters.repositories.payment_method_repo_impl import PaymentMethodRepoImpl
from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.application.dtos.oralsin_dtos import (
    OralsinContratoDTO,
)
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.entities.patient_entity import PatientEntity
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.installment_repository import (
    InstallmentRepository,
)
from plugins.django_interface.models import Installment as InstallmentModel


class InstallmentRepoImpl(InstallmentRepository):
    """
    Implementação concreta e segura do repositório de parcelas.
    """

    def __init__(self, mapper: OralsinPayloadMapper):
        self.mapper = mapper

    # ─────────────────────────── MÉTODOS DE PERSISTÊNCIA ───────────────────────────
    def save_many(self, installments: list[InstallmentEntity]) -> None:
        """
        Cria ou atualiza uma lista de parcelas, agora incluindo o campo 'schedule'.
        """
        if not installments:
            return

        oralsin_ids = [e.oralsin_installment_id for e in installments if e.oralsin_installment_id is not None]
        existing_map = {m.oralsin_installment_id: m for m in InstallmentModel.objects.filter(oralsin_installment_id__in=oralsin_ids)}

        to_create = []
        to_update = []
        UPDATE_FIELDS = [
            "due_date", "installment_amount", "received", "installment_status",
            "payment_method_id", "is_current", "installment_number", "contract_version",
            "schedule"
        ]

        pm_repo = PaymentMethodRepoImpl()

        for ent in installments:
            if ent.payment_method:
                pm = pm_repo.get_or_create_by_name(ent.payment_method.name)
                ent.payment_method.id = pm.id

            model = existing_map.get(ent.oralsin_installment_id)
            if model:
                has_changed = False
                for field in UPDATE_FIELDS:
                    new_value = (ent.payment_method.id if ent.payment_method else None) if field == "payment_method_id" else getattr(ent, field, None)

                    if getattr(model, field) != new_value:
                        setattr(model, field, new_value)
                        has_changed = True

                if has_changed:
                    to_update.append(model)
            else:
                to_create.append(InstallmentModel(
                    id=ent.id,
                    contract_id=ent.contract_id,
                    contract_version=ent.contract_version,
                    installment_number=ent.installment_number,
                    oralsin_installment_id=ent.oralsin_installment_id,
                    due_date=ent.due_date,
                    installment_amount=ent.installment_amount,
                    received=ent.received,
                    installment_status=ent.installment_status,
                    payment_method_id=ent.payment_method.id if ent.payment_method else None,
                    is_current=ent.is_current,
                    schedule=ent.schedule,
                    payer_id=ent.payer.id if ent.payer else None # Garante que o payer_id é salvo
                ))

        with transaction.atomic():
            if to_create:
                InstallmentModel.objects.bulk_create(to_create)
            if to_update:
                InstallmentModel.objects.bulk_update(to_update, UPDATE_FIELDS)
                
            
    @transaction.atomic
    def save(self, inst: InstallmentEntity) -> InstallmentEntity:
        """
        Cria ou atualiza uma parcela (Installment) no banco.
        """
        natural_key = dict(
            contract_id=inst.contract_id,
            contract_version=inst.contract_version,
            installment_number=inst.installment_number,
        )

        if inst.is_current:
            existing_current = InstallmentModel.objects.filter(
                contract_id=inst.contract_id,
                contract_version=inst.contract_version,
                is_current=True,
            ).first()

            if existing_current:
                natural_key["installment_number"] = existing_current.installment_number

            InstallmentModel.objects.filter(
                contract_id=inst.contract_id,
                contract_version=inst.contract_version,
                is_current=True,
            ).exclude(
                installment_number=natural_key["installment_number"]
            ).update(is_current=False)

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
            "payer_id": inst.payer.id if inst.payer else None, # Garante que o payer_id é salvo
        }

        try:
            model, _ = InstallmentModel.objects.update_or_create(
                **natural_key,
                defaults=defaults,
            )
        except IntegrityError:
            model = InstallmentModel.objects.get(**natural_key)
            for field, value in defaults.items():
                if field != "id":
                    setattr(model, field, value)
            model.save(update_fields=[f for f in defaults if f != "id"])

        return InstallmentEntity.from_model(model)
        
    def merge_installments(
        self,
        parcelas: list,
        contrato: OralsinContratoDTO | None,
        contract_id: str,
        patient_entity: PatientEntity, 
    ) -> list[InstallmentEntity]:
        """
        Combina os dados das parcelas em uma lista de entidades.
        """
        parcel_map = {}
        entities = self.mapper.map_installments(
            parcelas,
            contrato.versaoContrato,
            contract_id,
            patient_entity,
        )
        for ent in entities:
            key = (ent.contract_id, ent.contract_version, ent.installment_number)
            parcel_map[key] = ent
        return list(parcel_map.values())

    def delete(self, installment_id: str) -> None:
        InstallmentModel.objects.filter(id=installment_id).delete()

    def count_remaining_from_current(self, contract_id: uuid.UUID) -> int:
        current = (
            InstallmentModel.objects
            .filter(contract_id=contract_id, is_current=True)
            .only("installment_number")
            .first()
        )
        if not current:
            return 0

        return (
            InstallmentModel.objects
            .filter(
                contract_id=contract_id,
                received=False,
                installment_number__gte=current.installment_number,
            )
            .count()
        )
        
    def count_overdue_by_contract(self, contract_id: str) -> int:
        today = timezone.localdate()
        count = InstallmentModel.objects.filter(
            contract_id=contract_id,
            due_date__lt=today,
            received=False,
        ).count()
        return count

    def find_by_id(self, installment_id: str) -> InstallmentEntity | None:
        try:
            model = (
                InstallmentModel.objects.select_related("contract", "payment_method", "payer")
                .get(id=installment_id)
            )
            return InstallmentEntity.from_model(model)
        except InstallmentModel.DoesNotExist:
            return None

    def find_by_contract_ids(self, contract_ids: list[str]) -> list[InstallmentEntity]:
        if not contract_ids:
            return []
        qs = InstallmentModel.objects.select_related(
            "contract", "payment_method", "payer"
        ).filter(contract_id__in=contract_ids)
        return [InstallmentEntity.from_model(m) for m in qs]
    
    def get_current_installment(self, contract_id: str) -> InstallmentEntity | None:
        model = (
            InstallmentModel.objects
            .select_related('payer', 'payer__address', 'contract') 
            .prefetch_related('payer__phones') 
            .filter(contract_id=contract_id, is_current=True)
            .first()
        )
        return InstallmentEntity.from_model(model) if model else None
    
    def has_overdue(
        self, contract_id: str, min_days_overdue: int, *, contract_version: int | None = None
    ) -> bool:
        filters = {
            "contract_id": contract_id,
            "received": False,
            "due_date__lt": date.today() - timedelta(days=min_days_overdue),
        }
        if contract_version is not None:
            filters["contract_version"] = contract_version
        return InstallmentModel.objects.filter(**filters).exists()

    def _overdue(
        self,
        contract_id: str,
        min_days_overdue: int,
        offset: int,
        limit: int,
        is_current: bool = False,
        *,
        contract_version: int | None = None,
    ) -> PagedResult[InstallmentEntity]:
        filters = {
            "contract_id": contract_id,
            "received": False,
            "due_date__lt": date.today() - timedelta(days=min_days_overdue),
            "is_current": is_current,
        }
        if contract_version is not None:
            filters["contract_version"] = contract_version

        base_query = InstallmentModel.objects.filter(**filters).order_by("due_date")
        total = base_query.count()
        
        page_qs = base_query.select_related("contract", "payment_method", "payer")[offset : offset + limit]
        items = [InstallmentEntity.from_model(m) for m in page_qs]

        return PagedResult(
            items=items, total=total, page=(offset // limit) + 1, page_size=limit
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
            contract_id,
            min_days_overdue,
            offset,
            limit,
            is_current=True,
            contract_version=contract_version,
        )
    
    def get_trigger_installment(self, contract_id: str) -> InstallmentEntity | None:
        return self.get_current_installment(contract_id)

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[InstallmentEntity]:
        qs = InstallmentModel.objects.select_related("contract", "payment_method", "payer").all()

        clinic_id = filtros.pop("clinic_id", None)
        if clinic_id:
            qs = qs.filter(contract__clinic_id=clinic_id)

        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        page_qs = qs.order_by("due_date", "installment_number")[offset : offset + page_size]

        items = [InstallmentEntity.from_model(m) for m in page_qs]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
    
    def existing_oralsin_ids(self, ids: list[int]) -> set[int]:
        return set(
            InstallmentModel.objects
            .filter(oralsin_installment_id__in=ids)
            .values_list("oralsin_installment_id", flat=True)
        )

    @transaction.atomic
    def set_current_installment_atomically(
        self, *, contract_id: uuid.UUID, oralsin_installment_id: int | None = None
    ) -> None:
        InstallmentModel.objects.filter(contract_id=contract_id, is_current=True).update(is_current=False)

        target_installment = None
        if oralsin_installment_id is not None:
            target_installment = (
                InstallmentModel.objects
                .filter(contract_id=contract_id, oralsin_installment_id=oralsin_installment_id)
                .first()
            )
        else:
            today = timezone.localdate()
            target_installment = (
                InstallmentModel.objects
                .filter(
                    contract_id=contract_id,
                    received=False,
                    due_date__lt=today
                )
                .order_by("due_date")
                .first()
            )

        if target_installment:
            target_installment.is_current = True
            target_installment.save(update_fields=["is_current"])