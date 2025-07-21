from __future__ import annotations

import uuid

import structlog
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from oralsin_core.adapters.repositories.payment_method_repo_impl import PaymentMethodRepoImpl
from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.contract_entity import ContractEntity
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from plugins.django_interface.models import Contract as ContractModel
from plugins.django_interface.models import CoveredClinic

logger = structlog.get_logger(__name__)

class ContractRepoImpl(ContractRepository):
    # ─────────────────────────── consultas ────────────────────────────
    def find_by_id(self, contract_id: str) -> ContractEntity | None:
        try:
            return ContractEntity.from_model(ContractModel.objects.get(id=contract_id))
        except ContractModel.DoesNotExist:
            return None
        
    def find_by_patient_id(self, patient_id: str) -> ContractEntity | None:
        try:
            return ContractEntity.from_model(ContractModel.objects.get(patient_id=patient_id))
        except ContractModel.DoesNotExist:
            return None

    def exists(self, oralsin_contract_id: int, *, contract_version: str | None = None, patient_id: uuid.UUID | None = None) -> bool:
        filters: dict[str, object] = {"oralsin_contract_id": oralsin_contract_id}
        if contract_version is not None:
            filters["contract_version"] = str(contract_version)
        if patient_id is not None:
            filters["patient_id"] = patient_id
        return ContractModel.objects.filter(**filters).exists()
    
    def list_by_clinic(self, clinic_id: int) -> list[ContractEntity]:
        """
        Recebe `clinic_id` da Oralsin → resolve o UUID interno da `Clinic`
        a partir de `CoveredClinic` e devolve os contratos.
        """
        covered = None
        
        # 1. Verifica se o identificador fornecido é um UUID válido.
        #    Isso nos ajuda a decidir qual campo do banco de dados consultar.
        try:
            uuid.UUID(str(clinic_id))
            is_uuid = True
        except ValueError:
            is_uuid = False

        # 2. Usa um objeto Q para uma consulta mais limpa e eficiente.
        query = Q(clinic_id=clinic_id) if is_uuid else Q(oralsin_clinic_id=int(clinic_id))
            
        covered = CoveredClinic.objects.filter(query).first()

        if not covered:
            logger.warning(
                "covered_clinic_not_found",
                searched_id=clinic_id,
                message="Nenhuma clínica coberta (CoveredClinic) foi encontrada com o ID fornecido."
            )
            return []

        qs = ContractModel.objects.filter(clinic_id=covered.clinic)
        logger.debug(
            "contracts_found",
            clinic_id=clinic_id,
            internal_clinic_uuid=str(covered.id),
            contracts=qs.count(),
        )
        return [ContractEntity.from_model(m) for m in qs]

    # ────────────────────────── persistência ───────────────────────────
    @transaction.atomic
    def update(self, contract: ContractEntity) -> ContractEntity:
        """
        Atualiza **somente** contratos já existentes.
        Nunca cria um novo — se não existir, levanta `DoesNotExist`.
        """
        try:
            model = ContractModel.objects.filter(
                oralsin_contract_id=contract.oralsin_contract_id,
                contract_version=str(contract.contract_version),
                patient_id=contract.patient_id,
            ).first()
        except ContractModel.DoesNotExist:
            raise                     # deixamos o handler decidir o que fazer

        # 1) Payment method
        if contract.payment_method:
            pm_repo = PaymentMethodRepoImpl()
            pm_model = pm_repo.get_or_create_by_name(contract.payment_method.name)
            contract.payment_method.id = pm_model.id
            contract.payment_method.oralsin_payment_method_id = pm_model.oralsin_payment_method_id
            model.payment_method = pm_model

        # 2) Campos mutáveis
        updatable = (
            "status",
            "remaining_installments",
            "overdue_amount",
            "final_contract_value",
            "do_notifications",
            "do_billings",
            "first_billing_date",
            "negotiation_notes",
        )
        changed = False
        for field in updatable:
            new_val = getattr(contract, field, None)
            if getattr(model, field) != new_val:
                setattr(model, field, new_val)
                changed = True

        if changed:
            model.updated_at = timezone.now()
            model.save(update_fields=[*updatable, "payment_method", "updated_at"])

        return ContractEntity.from_model(model)
    
    @transaction.atomic
    def save(self, contract: ContractEntity) -> ContractEntity:
        pm_model = None
        if contract.payment_method:
            pm_repo = PaymentMethodRepoImpl()
            pm_model = pm_repo.get_or_create_by_name(contract.payment_method.name)
            contract.payment_method.id = pm_model.id

        lookup = {
            "oralsin_contract_id": contract.oralsin_contract_id,
            "contract_version"   : contract.contract_version,
            "patient_id"         : contract.patient_id,
        }
        
        defaults = {
            "clinic_id"              : contract.clinic_id,
            "status"                 : contract.status,
            "remaining_installments" : contract.remaining_installments,
            "overdue_amount"         : contract.overdue_amount,
            "final_contract_value"   : contract.final_contract_value,
            "do_notifications"       : contract.do_notifications,
            "do_billings"            : contract.do_billings,
            "first_billing_date"     : contract.first_billing_date,
            "negotiation_notes"      : contract.negotiation_notes,
            "payment_method"         : pm_model,
            "updated_at"             : timezone.now(),
        }

        model, _ = ContractModel.objects.update_or_create(defaults=defaults, **lookup)
        return ContractEntity.from_model(model)

    # ------------------------------------------------------------------
    def delete(self, contract_id: str) -> None:
        ContractModel.objects.filter(id=contract_id).delete()
        
    def qs(self):
        return ContractModel.objects.all()

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[ContractEntity]:
        """
        Retorna PagedResult contendo lista de ContractEntity e total,
        aplicando paginação sobre ContractModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = ContractModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        clinic_uuid = filtros.pop("clinic_id", None)
        if clinic_uuid:
            qs = qs.filter(clinic_id=clinic_uuid)

        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        contrato_page = qs.order_by('overdue_amount')[offset: offset + page_size]

        items = [ContractEntity.from_model(m) for m in contrato_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)