from datetime import datetime
from typing import Any, Literal, Union

import structlog
from django.utils import timezone
from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO

from notification_billing.core.domain.entities.contact_history_entity import ContactHistoryEntity
from notification_billing.core.domain.entities.contact_schedule_entity import (
    ContactScheduleEntity,
)
from notification_billing.core.domain.repositories.contact_history_repository import ContactHistoryRepository
from plugins.django_interface.models import Clinic as ClinicModel
from plugins.django_interface.models import (
    ContactHistory as ContactHistoryModel,
)
from plugins.django_interface.models import (
    ContactSchedule as ContactScheduleModel,
)
from plugins.django_interface.models import Contract as ContractModel
from plugins.django_interface.models import (
    Message as MessageModel,
)
from plugins.django_interface.models import Patient as PatientModel

ScheduleLike = Union[ContactScheduleModel, ContactScheduleEntity]  # noqa: UP007
ContactType = Literal["phonecall", "sms", "whatsapp", "email"]

_CONTACT_TYPE_DESC: dict[ContactType, str] = {
    "phonecall": "Ligação telefônica",
    "sms": "SMS",
    "whatsapp": "Mensagem via WhatsApp",
    "email": "E-mail",
}

class ContactHistoryRepoImpl(ContactHistoryRepository):
    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)
        self.api_client = OralsinAPIClient()
    
    # ------------------------------------------------------------------  aux
    @staticmethod
    def _friendly_description(contact_type: str) -> str:
        return _CONTACT_TYPE_DESC.get(contact_type, contact_type)
    
    # ------------------------------------------------------------------  save

    def save(self, history: ContactHistoryEntity) -> ContactHistoryEntity:
        model = ContactHistoryModel.objects.create(**history.to_dict())
        entity = ContactHistoryEntity.from_model(model)

        # tenta reportar à Oralsin
        try:
            patient = PatientModel.objects.get(id=entity.patient_id)
            clinic = ClinicModel.objects.get(id=entity.clinic_id)
            contract = None
            if entity.contract_id:
                contract = ContractModel.objects.filter(id=entity.contract_id).first()
            
            message_desc = "Sem mensagem registrada"
            if entity.message_id:
                message_obj = MessageModel.objects.filter(id=entity.message_id).first()
                if message_obj and getattr(message_obj, "content", None):
                    message_desc = message_obj.content
                
            payload = OralsinContatoHistoricoEnvioDTO(
                idClinica=clinic.oralsin_clinic_id,
                idPaciente=patient.oralsin_patient_id,
                idContrato=getattr(contract, "oralsin_contract_id", None),
                dataHoraInseriu=entity.sent_at or timezone.now(),
                observacao=entity.observation or "",
                contatoTipo=self._friendly_description(entity.contact_type),
                descricao=message_desc,
            )
            # self.api_client.post_contact_history(payload)
            self.log.info("Payload Contato -> Oralsin", payload=payload)
        except Exception as exc:  # noqa: BLE001
            self.log.error("oralsin_contact_history_failed", error=str(exc))

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

        # tenta reportar à Oralsin
        try:
            patient = PatientModel.objects.get(id=entity.patient_id)
            clinic = ClinicModel.objects.get(id=entity.clinic_id)
            contract = None
            if entity.contract_id:
                contract = ContractModel.objects.filter(id=entity.contract_id).first()

            message_desc = "Sem mensagem registrada"
            if entity.message_id:
                message_obj = MessageModel.objects.filter(id=entity.message_id).first()
                if message_obj and getattr(message_obj, "content", None):
                    message_desc = message_obj.content
                
            payload = OralsinContatoHistoricoEnvioDTO(
                idClinica=clinic.oralsin_clinic_id,
                idPaciente=patient.oralsin_patient_id,
                idContrato=getattr(contract, "oralsin_contract_id", None),
                dataHoraInseriu=entity.sent_at or timezone.now(),
                observacao=entity.observation or "",
                contatoTipo=self._friendly_description(entity.contact_type),
                descricao=message_desc,
            )
            # self.api_client.post_contact_history(payload)
            self.log.info("Payload Contato -> Oralsin", payload=payload)
        except Exception as exc:  # noqa: BLE001
            self.log.error("oralsin_contact_history_failed", error=str(exc))

        return entity

    # ------------------------------------------------------------------  find_by_id

    def find_by_id(self, history_id: str) -> ContactHistoryEntity | None:
        try:
            model = ContactHistoryModel.objects.get(id=history_id)
            return ContactHistoryEntity.from_model(model)
        except ContactHistoryModel.DoesNotExist:
            return None
