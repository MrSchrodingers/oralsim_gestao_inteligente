from datetime import datetime
from typing import Any, Union

import structlog
from django.db import transaction
from oralsin_core.core.application.cqrs import PagedResult

from notification_billing.core.domain.entities.contact_history_entity import ContactHistoryEntity
from notification_billing.core.domain.entities.contact_schedule_entity import (
    ContactScheduleEntity,
)
from notification_billing.core.domain.events.contact_history_events import ContactHistoryCreated
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from plugins.django_interface.models import (
    ContactHistory as ContactHistoryModel,
)
from plugins.django_interface.models import (
    ContactSchedule as ContactScheduleModel,
)

ScheduleLike = Union[ContactScheduleModel, ContactScheduleEntity]  # noqa: UP007

class ContactHistoryRepoImpl(ContactHistoryRepository):
    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)
    
    # ------------------------------------------------------------------  save

    def save(self, history: ContactHistoryEntity) -> ContactHistoryEntity:
        model = ContactHistoryModel.objects.create(**history.to_dict())
        entity = ContactHistoryEntity.from_model(model)

        transaction.on_commit(
            lambda: ContactHistoryCreated.emit(entity_id=entity.id)
        )
        return entity

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
            advance_flow=getattr(schedule, "advance_flow", True),
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
        entity = ContactHistoryEntity.from_model(model)

        transaction.on_commit(
            lambda: ContactHistoryCreated.emit(entity_id=entity.id)
        )
        return entity

    # ------------------------------------------------------------------  find_by_id
    def find_by_channel(self, contact_type: str) -> list[ContactHistoryEntity]:
        """Busca todos os históricos de um determinado canal/tipo de contato."""
        models = ContactHistoryModel.objects.filter(contact_type=contact_type).order_by("-sent_at")
        return [ContactHistoryEntity.from_model(model) for model in models]
    
    def filter(self, **filtros: Any) -> list[ContactHistoryEntity]:
        """
        Filtra o histórico de contatos com base em um dicionário de critérios.
        """
        channel = filtros.pop('channel', None)
        if channel:
            filtros['contact_type'] = channel

        qs = ContactHistoryModel.objects.filter(**filtros).order_by("-sent_at")
        return [ContactHistoryEntity.from_model(m) for m in qs]
        
    def find_by_id(self, history_id: str) -> ContactHistoryEntity | None:
        try:
            model = ContactHistoryModel.objects.get(id=history_id)
            return ContactHistoryEntity.from_model(model)
        except ContactHistoryModel.DoesNotExist:
            return None

    def get_latest_by_clinic(self, clinic_id: str, limit: int = 5) -> list[ContactHistoryEntity]:
        """
        Busca os últimos N registros de histórico de contato para uma clínica,
        ordenados pelo mais recente.

        Args:
            clinic_id: O ID da clínica a ser consultada.
            limit: O número máximo de registros a serem retornados.

        Returns:
            Uma lista de entidades `ContactHistoryEntity`. O nome do paciente
            é adicionado dinamicamente ao atributo `patient_name` de cada
            entidade para uso no relatório.
        """
        latest_models = (
            ContactHistoryModel.objects
            .filter(clinic_id=clinic_id)
            .select_related('patient')  # Otimização para pré-buscar dados do paciente
            .order_by("-sent_at")
            [:limit]
        )

        entities = []
        for model in latest_models:
            entity = ContactHistoryEntity.from_model(model)

            # Adiciona dinamicamente o nome do paciente à entidade para fácil acesso no PDF
            if model.patient and hasattr(model.patient, 'name'):
                entity.patient_name = model.patient.name
            else:
                entity.patient_name = "Paciente Desconhecido"
            
            entities.append(entity)

        return entities
    
    def list(
        self, filtros: dict[str, Any] | None, page: int, page_size: int
    ) -> PagedResult[ContactHistoryEntity]:
        """
        lista com paginação genérica.
        """
        qs = ContactHistoryModel.objects.all()
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        objs_page = qs.order_by("sent_at")[offset : offset + page_size]

        items = [ContactHistoryEntity.from_model(obj) for obj in objs_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)