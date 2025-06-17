from __future__ import annotations

import structlog
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

    def list_by_clinic(self, clinic_id: int) -> list[ContractEntity]:
        """
        Recebe `clinic_id` da Oralsin → resolve o UUID interno da `Clinic`
        a partir de `CoveredClinic` e devolve os contratos.
        """
        try:
            covered = CoveredClinic.objects.get(
                Q(clinic_id=clinic_id) | Q(oralsin_clinic_id=clinic_id)
            )
        except CoveredClinic.DoesNotExist:
            logger.warning("covered_clinic_not_found", clinic_id=clinic_id)
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
    def save(self, contract: ContractEntity) -> ContractEntity:
        # 1) resolve FK de PaymentMethod
        pm_model = None
        if contract.payment_method:
            pm_model = PaymentMethodRepoImpl().get_or_create_by_name(
                contract.payment_method.name
            )
            contract.payment_method.id = pm_model.id
            contract.payment_method.oralsin_payment_method_id = (
                pm_model.oralsin_payment_method_id
            )

        # 2) fields que queremos atualizar / criar
        defaults = {
            "patient_id": contract.patient_id,
            "clinic_id": contract.clinic_id,
            "status": contract.status,
            "contract_version": contract.contract_version,
            "remaining_installments": contract.remaining_installments,
            "overdue_amount": contract.overdue_amount,
            "final_contract_value": contract.final_contract_value,
            "do_notifications": contract.do_notifications,
            "do_billings": contract.do_billings,
            "first_billing_date": contract.first_billing_date,
            "negotiation_notes": contract.negotiation_notes,
            "payment_method": pm_model,
            "updated_at": timezone.now(),
        }

        # 3) lookup apenas por (oralsin_contract_id, contract_version)
        lookup = {
            "oralsin_contract_id": contract.oralsin_contract_id,
            "contract_version": contract.contract_version,
        }

        # 4) upsert
        model, _created = ContractModel.objects.update_or_create(
            defaults=defaults,
            **lookup
        )
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