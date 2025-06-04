from collections.abc import Sequence

from notification_billing.core.domain.entities.flow_step_config_entity import FlowStepConfigEntity
from notification_billing.core.domain.repositories.flow_step_config_repository import FlowStepConfigRepository
from plugins.django_interface.models import FlowStepConfig as FlowStepConfigModel


class FlowStepConfigRepoImpl(FlowStepConfigRepository):
    def find_by_step(self, step_number: int) -> FlowStepConfigEntity | None:
        try:
            m = FlowStepConfigModel.objects.get(step_number=step_number)
            return FlowStepConfigEntity.from_model(m)
        except FlowStepConfigModel.DoesNotExist:
            return None

    def _all(self) -> list[FlowStepConfigEntity]:
        return [FlowStepConfigEntity.from_model(m) for m in FlowStepConfigModel.objects.all()]
    
    def list_active_steps(self) -> Sequence[FlowStepConfigEntity]:
        return self._all()