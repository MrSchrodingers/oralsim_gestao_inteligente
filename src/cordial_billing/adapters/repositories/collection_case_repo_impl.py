from typing import Any

from django.db.models import Count, Sum
from oralsin_core.core.application.cqrs import PagedResult

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
    def find_by_id(self, collection_case_id: str) -> CollectionCaseEntity | None:
        try:
            m = CaseModel.objects.get(id=collection_case_id)
            return CollectionCaseEntity.from_model(m)
        except CaseModel.DoesNotExist:
            return None


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
            "stage_id": case.stage_id,  # Adicionado para persistência
            "last_stage_id": case.last_stage_id,
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
        # ✨ CORREÇÃO APLICADA AQUI ✨
        return CollectionCaseEntity(
            id=model.id,
            patient_id=model.patient_id,
            contract_id=model.contract_id,
            installment_id=model.installment_id,
            clinic_id=model.clinic_id,
            opened_at=model.opened_at,
            amount=model.amount,
            stage_id=model.stage_id,  # Adicionado para retorno
            deal_sync_status=model.deal_sync_status,
            deal_id=model.deal_id,
            last_stage_id=model.last_stage_id,
            status=model.status,
        )

    def exists_for_installment(self, installment_id: str) -> bool:
        return CaseModel.objects.filter(installment_id=installment_id).exists()

    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[CollectionCaseEntity]:
        """
        lista com paginação genérica.
        """
        qs = CaseModel.objects.all()
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        objs_page = qs.order_by("deal_id")[offset : offset + page_size]

        items = [CollectionCaseEntity.from_model(obj) for obj in objs_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
    
    
    def get_summary_by_clinic(self, clinic_id: str) -> dict[str, Any]:
        """
        Calcula um sumário de casos de cobrança para uma clínica específica,
        agrupando por status e totalizando valores.

        Este método realiza uma única consulta ao banco de dados para agregar
        os dados de forma eficiente.

        Args:
            clinic_id: O ID da clínica para a qual o sumário será gerado.

        Returns:
            Um dicionário contendo:
            - "total_cases": O número total de casos de cobrança para a clínica.
            - "by_status": Uma lista de dicionários, onde cada um contém
              'status', 'count' (número de casos) e 'total_value' (soma dos valores).
        """
        # Filtra os casos da clínica especificada
        cases_for_clinic = CaseModel.objects.filter(clinic_id=clinic_id)

        # 1. Calcula o total de casos
        total_cases = cases_for_clinic.count()

        # 2. Agrupa por status, contando o número de casos e somando os valores
        summary_by_status = (
            cases_for_clinic.values("status")
            .annotate(
                count=Count("id"),
                total_value=Sum("amount"),
            )
            .order_by("-count")  # Ordena para mostrar os status com mais casos primeiro
        )

        # 3. Monta o dicionário de resultado final
        result = {
            "total_cases": total_cases,
            "by_status": list(summary_by_status),
        }

        return result