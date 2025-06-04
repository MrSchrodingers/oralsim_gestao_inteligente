from datetime import datetime
from typing import Any, Union

from notification_billing.core.domain.entities.contact_history_entity import ContactHistoryEntity
from notification_billing.core.domain.entities.contact_schedule_entity import (
    ContactScheduleEntity,  # se existir
)
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from plugins.django_interface.models import (
    ContactHistory as ContactHistoryModel,
)
from plugins.django_interface.models import (
    ContactSchedule as ContactScheduleModel,
)

ScheduleLike = Union[ContactScheduleModel, ContactScheduleEntity]  # noqa: UP007


class ContactHistoryRepoImpl(ContactHistoryRepository):
    # ------------------------------------------------------------------  save

    def save(self, history: ContactHistoryEntity) -> ContactHistoryEntity:
        model = ContactHistoryModel.objects.create(**history.to_dict())
        return ContactHistoryEntity.from_model(model)

    # ------------------------------------------------------------------  save_from_schedule

    def save_from_schedule(  # noqa: PLR0913
        self,
        schedule: ScheduleLike,
        sent_at: datetime,
        success: bool,
        channel: str,
        feedback: str | None = None,
        observation: str | None = None,
        message: Any | None = None,
    ) -> ContactHistoryEntity:
        """
        Persiste ContactHistory vindo de um ContactSchedule (model ou entity).

        Sempre popula **ambas** as colunas FK e os respectivos *_id para
        garantir que filtros por ID funcionem.
        """
        # --- mapeia campos comuns -------------------------------------------------
        base_kwargs = dict(
            contact_type=channel,
            sent_at=sent_at,
            notification_trigger=getattr(schedule, "notification_trigger", "manual"),
            advance_flow=getattr(schedule, "advance_flow", False),
            feedback_status=feedback,
            observation=observation,
            success=success,
        )

        # --- relacionamentos / FKs ------------------------------------------------
        if isinstance(schedule, ContactScheduleModel):
            base_kwargs.update(
                patient=schedule.patient,
                contract=schedule.contract,
                clinic=schedule.clinic,
                schedule=schedule,
                # *_id também preenchidos para filtros rápidos
                patient_id=schedule.patient_id,
                contract_id=schedule.contract_id,
                clinic_id=schedule.clinic_id,
                schedule_id=schedule.id,
            )
        else:  # entity
            base_kwargs.update(
                patient_id=schedule.patient_id,
                contract_id=schedule.contract_id,
                clinic_id=schedule.clinic_id,
                schedule_id=schedule.id,
            )

        # --- mensagem -------------------------------------------------------------
        if message is not None:
            if hasattr(message, "id"):
                base_kwargs["message_id"] = message.id
            else:  # Django model
                base_kwargs["message"] = message

        # --- cria & devolve -------------------------------------------------------
        model = ContactHistoryModel.objects.create(**base_kwargs)
        return ContactHistoryEntity.from_model(model)

    # ------------------------------------------------------------------  find_by_id

    def find_by_id(self, history_id: str) -> ContactHistoryEntity | None:
        try:
            model = ContactHistoryModel.objects.get(id=history_id)
            return ContactHistoryEntity.from_model(model)
        except ContactHistoryModel.DoesNotExist:
            return None
