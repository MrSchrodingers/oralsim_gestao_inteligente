from __future__ import annotations

import structlog
from django.utils import timezone

from oralsin_core.core.domain.entities.contract_entity import ContractEntity
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from plugins.django_interface.models import Contract as ContractModel
from plugins.django_interface.models import CoveredClinic
from plugins.django_interface.models import PaymentMethod as PaymentMethodModel

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
            covered = CoveredClinic.objects.get(oralsin_clinic_id=clinic_id)
        except CoveredClinic.DoesNotExist:
            logger.warning("covered_clinic_not_found", oralsin_clinic_id=clinic_id)
            return []

        qs = ContractModel.objects.filter(clinic_id=covered.clinic_id)
        logger.debug(
            "contracts_found",
            oralsin_clinic_id=clinic_id,
            internal_clinic_uuid=str(covered.id),
            contracts=qs.count(),
        )
        return [ContractEntity.from_model(m) for m in qs]

    # ────────────────────────── persistência ───────────────────────────
    def save(self, contract: ContractEntity) -> ContractEntity:
        # 1) resolve FK de PaymentMethod
        pm_model = None
        if contract.payment_method:
            pm, _ = PaymentMethodModel.objects.get_or_create(
                oralsin_payment_method_id=contract.payment_method.oralsin_payment_method_id,
                defaults={"name": contract.payment_method.name},
            )
            pm_model = pm

        # 2) fields que queremos atualizar / criar
        defaults = {
            "patient_id": contract.patient_id,
            "clinic_id": contract.clinic_id,
            "status": contract.status,
            "remaining_installments": contract.remaining_installments,
            "overdue_amount": contract.overdue_amount,
            "valor_contrato_final": contract.valor_contrato_final,
            "realizar_cobranca": contract.realizar_cobranca,
            "first_billing_date": contract.first_billing_date,
            "negotiation_notes": contract.negotiation_notes,
            "payment_method": pm_model,
            "updated_at": timezone.now(),
        }

        # 3) lookup apenas por (oralsin_contract_id, contract_version)
        lookup = {
            "oralsin_contract_id": contract.oralsin_contract_id,
            "contract_version": contract.contract_version or 1,
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
