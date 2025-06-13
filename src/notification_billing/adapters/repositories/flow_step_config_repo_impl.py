from collections.abc import Sequence
from typing import Any

from oralsin_core.core.application.cqrs import PagedResult

from notification_billing.core.domain.entities.flow_step_config_entity import FlowStepConfigEntity
from notification_billing.core.domain.repositories.flow_step_config_repository import (
    FlowStepConfigRepository,
)
from plugins.django_interface.models import FlowStepConfig as FlowStepConfigModel


class FlowStepConfigRepoImpl(FlowStepConfigRepository):
    """Implementação baseada nos models Django."""

    def find_by_step(self, step_number: int) -> FlowStepConfigEntity | None:
        try:
            m = FlowStepConfigModel.objects.get(step_number=step_number)
            return FlowStepConfigEntity.from_model(m)
        except FlowStepConfigModel.DoesNotExist:
            return None
        
    def find_by_id(self, payment_method_id: int) -> FlowStepConfigEntity | None:
        try:
            m = FlowStepConfigModel.objects.get(id=payment_method_id)
            return FlowStepConfigEntity.from_model(m)
        except FlowStepConfigModel.DoesNotExist:
            return None

    def _all(self) -> list[FlowStepConfigEntity]:
        return [FlowStepConfigEntity.from_model(m) for m in FlowStepConfigModel.objects.all()]

    def list_active_steps(self) -> Sequence[FlowStepConfigEntity]:
        qs = FlowStepConfigModel.objects.filter(active=True).order_by("step_number")
        return [FlowStepConfigEntity.from_model(m) for m in qs]

    def get_active(self, step_number: int) -> FlowStepConfigEntity | None:
        try:
            m = FlowStepConfigModel.objects.get(step_number=step_number, active=True)
            return FlowStepConfigEntity.from_model(m)
        except FlowStepConfigModel.DoesNotExist:
            return None

    def max_active_step(self) -> int:
        last = (
            FlowStepConfigModel.objects.filter(active=True)
            .order_by("-step_number")
            .first()
        )
        return last.step_number if last else 0

    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[FlowStepConfigEntity]:
        """
        lista com paginação genérica.
        """
        qs = FlowStepConfigModel.objects.all()
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        objs_page = qs.order_by("step_number")[offset : offset + page_size]

        items = [FlowStepConfigEntity.from_model(obj) for obj in objs_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)