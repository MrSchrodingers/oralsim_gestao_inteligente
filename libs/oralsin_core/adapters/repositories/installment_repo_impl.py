from datetime import date, timedelta
from typing import Any

from django.db import IntegrityError, transaction

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from plugins.django_interface.models import Contract as ContractModel
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

    def find_by_contract_ids(self, contract_ids: list[str]) -> list[InstallmentEntity]:
        """
        Busca todas as parcelas associadas a uma lista de IDs de contrato
        em uma única consulta ao banco de dados.
        """
        if not contract_ids:
            return []
        
        # Utiliza o lookup `__in` para buscar todos os registros de uma vez
        qs = InstallmentModel.objects.filter(contract_id__in=contract_ids)
        
        # Converte os models do Django para as entidades de domínio
        return [InstallmentEntity.from_model(m) for m in qs]
    
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
            contract_version=contract_version,
            is_current=True,
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
        """
        Cria ou atualiza uma parcela (Installment) no banco. 
        Se inst.is_current for True, antes de salvar, tenta achar a parcela atual
        existente para o mesmo (contract_id, contract_version) e, se achar, 
        reutiliza o campo 'installment_number' dela para forçar um update
        em vez de um insert. Também limpa (set is_current=False) demais parcelas
        que estivessem marcadas como current para aquele contrato/version.
        """

        # 1) Definimos o natural_key considerando o installment_number que veio no DTO
        natural_key = dict(
            contract_id=inst.contract_id,
            contract_version=inst.contract_version,
            installment_number=inst.installment_number,
        )

        # 2) Se essa entidade veio com is_current=True, before de qualquer insert/update:
        if inst.is_current:
            # 2.1) Procuramos se já há uma parcela marcadamente 'current' para este contrato/version
            existing_current = InstallmentModel.objects.filter(
                contract_id=inst.contract_id,
                contract_version=inst.contract_version,
                is_current=True,
            ).first()

            if existing_current:
                # Se já existe, sobrescrevemos o 'installment_number' no natural_key para
                # forçar o update nesse registro, em vez de criar outro novo.
                natural_key["installment_number"] = existing_current.installment_number

            # 2.2) Em seguida, garantimos que nenhuma outra parcela fique marcada como current
            # (exceto aquela que estamos prestes a inserir/atualizar).
            InstallmentModel.objects.filter(
                contract_id=inst.contract_id,
                contract_version=inst.contract_version,
                is_current=True,
            ).exclude(
                installment_number=natural_key["installment_number"]
            ).update(is_current=False)

        # 3) Preparamos o dict de campos que vamos inserir/atualizar
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
            # 4) Chamamos update_or_create usando o natural_key ajustado acima.
            model, created = InstallmentModel.objects.update_or_create(
                **natural_key,
                defaults=defaults,
            )
        except IntegrityError:
            # 5) Se houve corrida e acabou violando a UniqueConstraint parcial,
            # buscamos pelo natural_key e atualizamos manualmente campo a campo
            model = InstallmentModel.objects.get(**natural_key)
            for field, value in defaults.items():
                if field != "id":
                    setattr(model, field, value)
            model.save(update_fields=[f for f in defaults if f != "id"])

        return InstallmentEntity.from_model(model)

    def get_trigger_installment(self, contract_id: str) -> InstallmentEntity | None:
        qs = InstallmentModel.objects.filter(
            contract_id=contract_id,
            is_current=True
        ).order_by("due_date")

        count = qs.count()
        if count > 1:
            print(
                f"[Warning] Encontradas {count} parcelas com is_current=True "
                f"para contract_id={contract_id} (get_trigger_installment)."
            )
        m = qs.first()
        return InstallmentEntity.from_model(m) if m else None

    def get_current_installment(self, contract_id: str) -> InstallmentEntity | None:
        """
        Retorna a parcela marcada como 'is_current=True' para o contrato.
        Se houver mais de uma, leva apenas a primeira ordenada por 'due_date'.
        Se não houver nenhuma, retorna None.
        """
        qs = InstallmentModel.objects.filter(
            contract_id=contract_id,
            is_current=True
        ).order_by("due_date")

        count = qs.count()
        if count > 1:
            print(
                f"[Warning] Encontradas {count} parcelas com is_current=True "
                f"para contract_id={contract_id}. Será usada a mais antiga."
            )
        m = qs.first()
        return InstallmentEntity.from_model(m) if m else None

    def delete(self, installment_id: str) -> None:
        InstallmentModel.objects.filter(id=installment_id).delete()

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[InstallmentEntity]:
        qs = InstallmentModel.objects.all()

        # --- filtro por clínica ---
        clinic_id = filtros.pop("clinic_id", None)
        if clinic_id:
            qs = qs.filter(contract__clinic_id=clinic_id) 
            # Se também veio contract_id, garantimos combinação
            qs = qs.filter(contract_id__in=ContractModel.objects.filter(
                    clinic_id=clinic_id).values_list("id", flat=True))

        # --- demais filtros restam iguais ---
        if filtros:
            qs = qs.filter(**filtros)

        total   = qs.count()
        offset  = (page - 1) * page_size
        page_qs = qs.order_by("id")[offset: offset + page_size]

        items = [InstallmentEntity.from_model(m) for m in page_qs]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
