from cordial_billing.core.domain.entities.collection_case_entity import (
    CollectionCaseEntity,
)
from cordial_billing.core.domain.repositories.collection_case_repository import (
    CollectionCaseRepository,
)
from plugins.django_interface.models import CollectionCase
from plugins.django_interface.models import CollectionCase as CaseModel


class CollectionCaseRepoImpl(CollectionCaseRepository):
    """
    Persistência de `CollectionCase` via Django ORM, agora incluindo
    controle de deal_sync_status conforme deal_id.
    """

    def save(self, case: CollectionCaseEntity) -> CollectionCaseEntity:
        """
        Cria ou atualiza o CollectionCase com base no próprio ID e ajusta
        `deal_sync_status` automaticamente:
          - Se deal_id for None → status fica "pending"
          - Se deal_id não for None e registro novo (created) → status "created"
          - Se deal_id não for None e registro já existia antes → status "updated"
        """

        # 1) determina qual será o deal_sync_status antes de persistir:
        if case.deal_id is None:
            desired_sync_status = CollectionCase.DealSyncStatus.PENDING
        else:
            # se existir um registro prévio com esse ID, marcamos como UPDATED,
            # caso contrário, CREATED
            exists = CaseModel.objects.filter(id=case.id).exists()
            desired_sync_status = (
                CollectionCase.DealSyncStatus.UPDATED
                if exists
                else CollectionCase.DealSyncStatus.CREATED
            )

        # 2) campos que queremos atualizar ou criar
        defaults = {
            "patient_id": case.patient_id,
            "contract_id": case.contract_id,
            "installment_id": case.installment_id,
            "clinic_id": case.clinic_id,
            "opened_at": case.opened_at,
            "amount": case.amount,
            "deal_id": case.deal_id,
            "deal_sync_status": desired_sync_status,
            "status": case.status,
        }

        # 3) executa upsert pelo próprio id
        model, created = CaseModel.objects.update_or_create(
            id=case.id,
            defaults=defaults,
        )

        # 4) devolve a entidade refletindo o registro salvo
        return CollectionCaseEntity(
            id=model.id,
            patient_id=model.patient_id,
            contract_id=model.contract_id,
            installment_id=model.installment_id,
            clinic_id=model.clinic_id,
            opened_at=model.opened_at,
            amount=model.amount,
            deal_id=model.deal_id,
            status=model.status,
        )

    def exists_for_installment(self, installment_id: str) -> bool:
        return CaseModel.objects.filter(installment_id=installment_id).exists()
