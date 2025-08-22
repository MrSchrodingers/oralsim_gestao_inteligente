from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone
from oralsin_core.core.application.cqrs import PagedResult

from notification_billing.core.domain.entities.pending_call_entity import (
    PendingCallEntity,
)
from notification_billing.core.domain.repositories.pending_call_repository import (
    PendingCallRepository,
)
from plugins.django_interface.models import PendingCall as PendingCallModel


class PendingCallRepoImpl(PendingCallRepository):
    """Implementação Django do PendingCallRepository."""

    # ────────────────────────────────── #
    # CRUD básicos
    # ────────────────────────────────── #
    @transaction.atomic
    def create(  # noqa: PLR0913
        self,
        *,
        patient_id: str,
        contract_id: str,
        clinic_id: str,
        schedule_id: str | None,
        current_step: int,
        scheduled_at: datetime,
    ) -> PendingCallEntity:
        """Cria (ou retorna existente) a pendência de ligação para o step.

        A unicidade é garantida pelo UniqueConstraint:
        `('patient', 'contract', 'current_step', status='pending')`.
        """
        obj, _ = PendingCallModel.objects.update_or_create(
            patient_id=patient_id,
            contract_id=contract_id,
            current_step=current_step,
            status=PendingCallModel.Status.PENDING,
            defaults=dict(
                clinic_id=clinic_id,
                schedule_id=schedule_id,
                scheduled_at=scheduled_at,
            ),
        )
        return PendingCallEntity.from_model(obj)

    # ────────────────────────────────── #
    # Atualização de status
    # ────────────────────────────────── #
    @transaction.atomic
    def set_done(self, call_id: str, success: bool, notes: str | None = None) -> None:
        status = PendingCallModel.Status.DONE if success else PendingCallModel.Status.FAILED

        obj = (PendingCallModel.objects
               .select_for_update()
               .get(id=call_id))

        # idempotência: se já finalizada, não faz nada
        if obj.status in (PendingCallModel.Status.DONE, PendingCallModel.Status.FAILED):
            return

        obj.status = status
        obj.last_attempt_at = timezone.now()
        obj.attempts = (obj.attempts or 0) + 1
        obj.result_notes = notes
        obj.save(update_fields=["status","last_attempt_at","attempts","result_notes","updated_at"])

    # ────────────────────────────────── #
    # Consultas
    # ────────────────────────────────── #
    def find_by_id(self, pending_call_id: str) -> PendingCallEntity | None:
        try:
            m = PendingCallModel.objects.get(id=pending_call_id)
            return PendingCallEntity.from_model(m)
        except PendingCallModel.DoesNotExist:
            return None
        
    def list_pending(
        self, clinic_id: str, before: datetime
    ) -> list[PendingCallEntity]:
        qs = (
            PendingCallModel.objects.filter(
                clinic_id=clinic_id,
                status=PendingCallModel.Status.PENDING,
                scheduled_at__lte=before,
            )
            .order_by("scheduled_at")
            .select_related("patient", "contract")
        )
        return [PendingCallEntity.from_model(obj) for obj in qs]

    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[PendingCallEntity]:
        """
        lista com paginação genérica.

        Exemplo de `filtros`:
        ```
        {
            "clinic_id": "…",
            "status": PendingCallModel.Status.PENDING,
            "scheduled_at__date__lte": "2025-06-10"
        }
        ```
        """
        qs = PendingCallModel.objects.all()
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        objs_page = qs.order_by("scheduled_at")[offset : offset + page_size]

        items = [PendingCallEntity.from_model(obj) for obj in objs_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
