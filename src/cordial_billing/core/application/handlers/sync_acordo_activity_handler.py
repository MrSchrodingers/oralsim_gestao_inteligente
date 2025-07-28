from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from re import sub

from asgiref.sync import sync_to_async
from django.db.models import Max, Value
from django.db.models.expressions import F, Func
from django.utils import timezone
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from structlog import get_logger

from cordial_billing.core.application.commands.sync_acordo_activity_commands import (
    SyncAcordoActivitiesCommand,
)
from cordial_billing.core.domain.entities.pipedrive_activity_entity import (
    PipedriveActivityEntity,
)
from cordial_billing.core.domain.repositories.activity_repository import (
    ActivityRepository,
)
from cordial_billing.core.domain.repositories.deal_repository import DealRepository
from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ
from notification_billing.core.application.cqrs import CommandHandler
from plugins.django_interface.models import (
    Clinic as ClinicModel,
)
from plugins.django_interface.models import (
    Contract as ContractModel,
)
from plugins.django_interface.models import (
    CoveredClinic as CoveredClinicModel,
)
from plugins.django_interface.models import (
    Patient as PatientModel,
)
from plugins.django_interface.models import (
    PipeboardActivitySent,
)

log = get_logger(__name__)

_ACTIVITY_DESC = {"acordo_fechado": "Acordo fechado"}
BATCH_ROUTING_KEY = "acordo_fechado"
EXCHANGE = "oralsin.activities"
DLX = f"{EXCHANGE}.dlx"


class RegexReplace(Func):
    function = "regexp_replace"
    arity = 4


class SyncAcordoActivitiesHandler(CommandHandler[SyncAcordoActivitiesCommand]):
    """
    Lê atividades acordo_fechado (acordo fechado) do Pipeboard, mapeia paciente + contrato
    em nosso banco e publica o contato-histórico na fila “oralsin.activities”.
    """

    def __init__(  # noqa: PLR0913
        self,
        activity_repo: ActivityRepository,
        patient_repo: PatientRepository,
        contract_repo: ContractRepository,
        deal_repo: DealRepository,
        rabbit: RabbitMQ,
    ):
        self.activity_repo = activity_repo
        self.patient_repo = patient_repo
        self.contract_repo = contract_repo
        self.deal_repo = deal_repo
        self.rabbit = rabbit

        # artefatos de fila – declara uma única vez
        self.rabbit.declare_exchange(EXCHANGE, dlx=DLX)
        self.rabbit.declare_exchange(DLX, exchange_type="fanout")
        self.rabbit.declare_queue(EXCHANGE, dlx=DLX)
        self.rabbit.bind_queue(EXCHANGE, EXCHANGE, BATCH_ROUTING_KEY)

        # caches in-memory para reduzir round-trips
        self._patient_cache: dict[int, PatientModel] = {}           # key = deal_id
        self._contract_cache: dict[str, ContractModel | None] = {}  # key = patient.uuid

    async def handle(self, cmd: SyncAcordoActivitiesCommand) -> dict[str, int]:
        sent = skipped = 0
        log.info("sync_acordo_start", clinic_id=cmd.clinic_id, after_id=cmd.after_id)

        # 0️⃣ Carrega CoveredClinic + Clinic numa única query
        coverage_clinic: CoveredClinicModel = await sync_to_async(
            lambda: CoveredClinicModel.objects.select_related("clinic").get(
                oralsin_clinic_id=cmd.clinic_id
            )
        )()
        clinic: ClinicModel = coverage_clinic.clinic
        log.debug("loaded_clinic", clinic_id=clinic.id, clinic_name=clinic.name)

        # 🔢 se caller não informou after_id, descobre o último processado
        if cmd.after_id == 0:
            cmd.after_id = await sync_to_async(
                lambda: PipeboardActivitySent.objects.aggregate(
                    m=Max("activity_id")
                ).get("m")
                or 0
            )()
            log.debug("resolved_after_id", after_id=cmd.after_id)

        # ▶ Processa em lotes
        async for batch in self._producer_batches(cmd):
            log.info("processing_batch", batch_size=len(batch), start_id=batch[0].id, end_id=batch[-1].id)

            results = await asyncio.gather(
                *(self._process_entity(act, clinic) for act in batch)
            )

            batch_sent = sum(1 for ok in results if ok)
            batch_skipped = len(results) - batch_sent
            sent += batch_sent
            skipped += batch_skipped

            log.info(
                "batch_result",
                sent=batch_sent,
                skipped=batch_skipped,
                cumulative_sent=sent,
                cumulative_skipped=skipped,
            )

            # persiste IDs já processados (bulk)
            await sync_to_async(
                PipeboardActivitySent.objects.bulk_create,
                thread_sensitive=True,
            )(
                [PipeboardActivitySent(activity_id=act.id) for act in batch],
                ignore_conflicts=True,
            )

        log.info("sync_acordo_finished", sent=sent, skipped=skipped)
        return {"sent": sent, "skipped": skipped}

    async def _producer_batches(
        self, cmd: SyncAcordoActivitiesCommand
    ) -> AsyncGenerator[list[PipedriveActivityEntity]]:
        after = cmd.after_id
        while True:
            batch = await self.activity_repo.list_acordo_fechado(after, cmd.batch_size)
            if not batch:
                log.debug("no_more_batches", after_id=after)
                break
            yield batch
            after = batch[-1].id

    async def _process_entity(
        self, act: PipedriveActivityEntity, clinic: ClinicModel
    ) -> bool:
        log.debug("processing_activity", activity_id=act.id, deal_id=act.deal_id, person_id=act.person_id)
        try:
            patient = await self._get_patient(act.deal_id)
            if not patient:
                log.warning("skip_no_patient", activity_id=act.id, deal_id=act.deal_id)
                return False

            contract = await self._get_contract(patient.id)
            if not contract:
                log.warning("skip_no_contract", activity_id=act.id, patient_id=patient.id)
                return False

            payload = OralsinContatoHistoricoEnvioDTO(
                idClinica=clinic.oralsin_clinic_id,
                idPaciente=patient.oralsin_patient_id,
                idContrato=contract.oralsin_contract_id,
                dataHoraInseriu=(
                    act.marked_as_done_time
                    or act.update_time
                    or act.add_time
                    or timezone.now()
                ),
                observacao=act.note or "",
                contatoTipo=_ACTIVITY_DESC.get(act.type, act.type),
                descricao=act.subject or "Acordo fechado no Pipedrive",
            )

            self.rabbit.publish(
                EXCHANGE, BATCH_ROUTING_KEY, payload.model_dump(mode="json")
            )
            log.debug("activity_queued", activity_id=act.id)
            return True

        except Exception as exc:
            log.error("activity_failed", activity_id=act.id, error=str(exc))
            return False

    async def _get_patient(self, deal_id: int) -> PatientModel | None:
        if deal_id in self._patient_cache:
            log.debug("patient_cache_hit", deal_id=deal_id)
            return self._patient_cache[deal_id]

        log.debug("patient_cache_miss", deal_id=deal_id)
        deal_cpf = await self.deal_repo.find_cpf_by_deal_id(deal_id)
        normalized_cpf = sub(r"\D", "", deal_cpf or "")
        if not normalized_cpf:
            log.warning("missing_cpf", deal_id=deal_id)
            return None

        def qs_get_patient_by_cpf():
            return (
                PatientModel.objects
                .annotate(
                    cpf_only_digits=RegexReplace(
                        F("cpf"),
                        Value(r"\D"),
                        Value(""),
                        Value("g"),
                    )
                )
                .filter(cpf_only_digits=normalized_cpf)
                .first()
            )

        patient = await sync_to_async(qs_get_patient_by_cpf)()
        if patient:
            log.debug("loaded_patient", deal_id=deal_id, patient_id=patient.id)
            self._patient_cache[deal_id] = patient
        else:
            log.warning("no_patient_found", deal_id=deal_id, normalized_cpf=normalized_cpf)
        return patient

    async def _get_contract(self, patient_uuid: str) -> ContractModel | None:
        if patient_uuid in self._contract_cache:
            log.debug("contract_cache_hit", patient_uuid=patient_uuid)
            return self._contract_cache[patient_uuid]

        log.debug("contract_cache_miss", patient_uuid=patient_uuid)

        def qs_first():
            return (
                ContractModel.objects.filter(patient_id=patient_uuid)
                .order_by("-updated_at")
                .first()
            )

        contract = await sync_to_async(qs_first)()
        if contract:
            log.debug("loaded_contract", patient_uuid=patient_uuid, contract_id=contract.id)
        else:
            log.warning("no_contract_found", patient_uuid=patient_uuid)
        self._contract_cache[patient_uuid] = contract
        return contract
