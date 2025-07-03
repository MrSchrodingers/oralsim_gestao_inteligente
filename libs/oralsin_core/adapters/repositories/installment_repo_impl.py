from __future__ import annotations

import uuid
from datetime import date, timedelta

from django.db import IntegrityError, transaction

from oralsin_core.adapters.repositories.payment_method_repo_impl import PaymentMethodRepoImpl
from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.application.dtos.oralsin_dtos import (
    OralsinContratoDTO,
    OralsinParcelaAtualDetalheDTO,
)
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.installment_repository import (
    InstallmentRepository,
)
from plugins.django_interface.models import Installment as InstallmentModel


class InstallmentRepoImpl(InstallmentRepository):
    """
    Implementação concreta e segura do repositório de parcelas.

    Esta versão foi refatorada para garantir a segurança dos dados, otimizar
    as consultas e manter total compatibilidade com a interface
    abstrata 'InstallmentRepository'.
    """

    def __init__(self, mapper: OralsinPayloadMapper):
        self.mapper = mapper

    # ─────────────────────────── MÉTODOS DE PERSISTÊNCIA ───────────────────────────
    def save_many(self, installments: list[InstallmentEntity]) -> None:
        """
        [NOVO E CORRIGIDO] Cria ou atualiza uma lista de parcelas de forma eficiente,
        segura e em lote.
        """
        if not installments:
            return

        oralsin_ids = [e.oralsin_installment_id for e in installments if e.oralsin_installment_id is not None]
        existing_map = {m.oralsin_installment_id: m for m in InstallmentModel.objects.filter(oralsin_installment_id__in=oralsin_ids)}
        
        to_create = []
        to_update = []
        UPDATE_FIELDS = [
            "due_date", "installment_amount", "received", "installment_status",
            "payment_method_id", "is_current", "installment_number", "contract_version"
        ]

        pm_repo = PaymentMethodRepoImpl()

        for ent in installments:
            # Garante que o método de pagamento tenha um ID antes de persistir
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
                ))

        with transaction.atomic():
            if to_create:
                InstallmentModel.objects.bulk_create(to_create, ignore_conflicts=True)
            if to_update:
                InstallmentModel.objects.bulk_update(to_update, UPDATE_FIELDS)
                
            
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
        
    def merge_installments(
        self,
        parcelas: list,
        contrato: OralsinContratoDTO | None,
        parcela_atual: OralsinParcelaAtualDetalheDTO | None,
        contract_id: str,
    ) -> list[InstallmentEntity]:
        """
        Combina os dados das parcelas em uma lista de entidades.

        Esta lógica de transformação de dados é mantida aqui para cumprir o contrato
        da interface 'InstallmentRepository'.
        """
        parcel_map = {}
        # Mapeia todas as parcelas usando o mapper injetado.
        entities = self.mapper.map_installments(
            parcelas, contrato.versaoContrato, contract_id
        )
        for ent in entities:
            # A chave garante a unicidade por contrato, versão e número da parcela.
            key = (ent.contract_id, ent.contract_version, ent.installment_number)
            parcel_map[key] = ent
        return list(parcel_map.values())

    def delete(self, installment_id: str) -> None:
        """Remove uma parcela pelo seu ID."""
        InstallmentModel.objects.filter(id=installment_id).delete()

    # ──────────────────────────── MÉTODOS DE CONSULTA ────────────────────────────

    def find_by_id(self, installment_id: str) -> InstallmentEntity | None:
        """Recupera parcela por ID com dados relacionados."""
        try:
            model = (
                InstallmentModel.objects.select_related("contract", "payment_method")
                .get(id=installment_id)
            )
            return InstallmentEntity.from_model(model)
        except InstallmentModel.DoesNotExist:
            return None

    def find_by_contract_ids(self, contract_ids: list[str]) -> list[InstallmentEntity]:
        """Busca todas as parcelas para uma lista de contratos."""
        if not contract_ids:
            return []
        qs = InstallmentModel.objects.select_related(
            "contract", "payment_method"
        ).filter(contract_id__in=contract_ids)
        return [InstallmentEntity.from_model(m) for m in qs]
    
    def has_overdue(
        self, contract_id: str, min_days_overdue: int, *, contract_version: int | None = None
    ) -> bool:
        """Verifica eficientemente se existem parcelas vencidas."""
        filters = {
            "contract_id": contract_id,
            "received": False,
            "due_date__lt": date.today() - timedelta(days=min_days_overdue),
        }
        if contract_version is not None:
            filters["contract_version"] = contract_version

        # .exists() é a forma mais performática para esta verificação.
        return InstallmentModel.objects.filter(**filters).exists()

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
        """Helper interno para consultas de parcelas vencidas."""
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
        
        page_qs = base_query.select_related("contract", "payment_method")[offset : offset + limit]
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
        """lista parcelas vencidas paginadas."""
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
        """lista a parcela atual se ela estiver vencida."""
        return self._overdue(
            contract_id,
            min_days_overdue,
            offset,
            limit,
            is_current=True,
            contract_version=contract_version,
        )
    
    def get_current_installment(self, contract_id: str) -> InstallmentEntity | None:
        """[CONSOLIDADO] Recupera a parcela marcada como 'is_current'."""
        qs = InstallmentModel.objects.select_related(
            "contract", "payment_method"
        ).filter(contract_id=contract_id, is_current=True).order_by("due_date")
        
        # A implementação é a mesma para 'get_current_installment' e 'get_trigger_installment'.
        if qs.count() > 1:
            print(f"[Warning] Múltiplas parcelas 'current' para o contrato {contract_id}.")

        model = qs.first()
        return InstallmentEntity.from_model(model) if model else None

    def get_trigger_installment(self, contract_id: str) -> InstallmentEntity | None:
        """[CONSOLIDADO] Recupera a parcela de gatilho (considerada a 'current')."""
        # A lógica de negócio definiu que a parcela de "gatilho" é a parcela "atual".
        return self.get_current_installment(contract_id)

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[InstallmentEntity]:
        """[CORRIGIDO] Retorna lista paginada de parcelas aplicando filtros."""
        qs = InstallmentModel.objects.select_related("contract", "payment_method").all()

        clinic_id = filtros.pop("clinic_id", None)
        if clinic_id:
            # A forma correta e simplificada de filtrar pela clínica do contrato.
            qs = qs.filter(contract__clinic_id=clinic_id)

        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        page_qs = qs.order_by("contract__id", "installment_number")[offset : offset + page_size]

        items = [InstallmentEntity.from_model(m) for m in page_qs]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
    
    def existing_oralsin_ids(self, ids: list[int]) -> set[int]:
        return set(
            InstallmentModel.objects
            .filter(oralsin_installment_id__in=ids)
            .values_list("oralsin_installment_id", flat=True)
        )

    # ──────────────────────── MÉTODO ATÔMICO RECOMENDADO (NOVO) ─────────────────────────

    @transaction.atomic
    def set_current_installment_atomically(
        self, contract_id: uuid.UUID, oralsin_installment_id: int
    ) -> bool:
        """
        [NOVO E RECOMENDADO] Define a parcela 'current' de forma atômica e segura.

        Este método não faz parte da interface 'InstallmentRepository', mas é
        a forma recomendada de gerenciar a flag 'is_current' para evitar erros.
        """
        # Garante que nenhuma outra parcela seja 'current'
        InstallmentModel.objects.filter(contract_id=contract_id).update(is_current=False)

        # Define a parcela correta como 'current'
        updated_count = InstallmentModel.objects.filter(
            contract_id=contract_id, oralsin_installment_id=oralsin_installment_id
        ).update(is_current=True)

        return updated_count > 0