# ——————————————————————————————————————————————————————————
#  SyncInadimplenciaHandler – versão otimizada (bulk-safe)
#  · Mantém performance em bulk_create/bulk_update
#  · Garante **UMA** parcela is_current=True por (contract_id, contract_version)
#  · Evita violar a UNIQUE CONSTRAINT `unique_current_per_contract_version`
# ——————————————————————————————————————————————————————————
from __future__ import annotations

import cProfile
import io
import logging
import os
import pstats
import time
import uuid
from collections import defaultdict
from typing import Any

from django.conf import settings
from django.db import connection, models, transaction

from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.adapters.observability.metrics import (
    SYNC_DURATION,
    SYNC_PATIENTS,
    SYNC_RUNS,
)
from oralsin_core.adapters.repositories.payment_method_repo_impl import PaymentMethodRepoImpl
from oralsin_core.core.application.commands.sync_commands import SyncInadimplenciaCommand
from oralsin_core.core.application.cqrs import CommandHandler
from oralsin_core.core.application.dtos.oralsin_dtos import (
    InadimplenciaQueryDTO,
    OralsinPacienteDTO,
)
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import (
    InstallmentRepository,
)
from oralsin_core.core.domain.repositories.patient_phone_repository import (
    PatientPhoneRepository,
)
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from oralsin_core.core.domain.services.event_dispatcher import EventDispatcher
from plugins.django_interface.models import Installment as InstallmentModel
from plugins.django_interface.models import PatientPhone as PatientPhoneModel

# ────────────────────────────────  logger  ───────────────────────────────
logger = logging.getLogger(__name__)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(
        logging.Formatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s [%(funcName)s:%(lineno)d]"
        )
    )
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

PROFILE_ENABLED = os.getenv("PROFILE_SYNC_HANDLER", "true").lower() == "true"


class SyncInadimplenciaHandler(CommandHandler[SyncInadimplenciaCommand]):
    """
    Sincroniza inadimplência: pacientes, contratos e parcelas.
    NÃO dispara agendamentos ou notificações.
    """

    # ────────────────────────────  ctor  ────────────────────────────────
    def __init__(  # noqa: PLR0913
        self,
        api_client: OralsinAPIClient,
        clinic_repo: ClinicRepository,
        patient_repo: PatientRepository,
        phone_repo: PatientPhoneRepository,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        mapper: OralsinPayloadMapper,
        dispatcher: EventDispatcher,
    ) -> None:
        self.api = api_client
        self.clinic_repo = clinic_repo
        self.patient_repo = patient_repo
        self.phone_repo = phone_repo
        self.contract_repo = contract_repo
        self.installment_repo = installment_repo
        self.mapper = mapper
        self.dispatcher = dispatcher

    # ───────────────────── util p/ profiling local ──────────────────────
    def _profiled(self, name: str, fn, *args, **kwargs) -> Any:
        if not PROFILE_ENABLED:
            return fn(*args, **kwargs)
        start = time.perf_counter()
        before = len(connection.queries) if settings.DEBUG else 0
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - start
        after = len(connection.queries) if settings.DEBUG else 0
        delta = after - before if settings.DEBUG else "N/A"
        logger.info(f"[PROFILE] {name}: {elapsed:.3f}s, ΔQ={delta}")
        return result

    # ─────────────────────────────  main  ───────────────────────────────
    @transaction.atomic
    def handle(self, cmd: SyncInadimplenciaCommand) -> None:
        profiler = cProfile.Profile() if PROFILE_ENABLED else None
        if profiler:
            profiler.enable()

        SYNC_RUNS.labels(str(cmd.oralsin_clinic_id)).inc()
        start = time.perf_counter()

        # 1) clínica
        clinic = self._profiled(
            "clinic.get_or_create",
            self.clinic_repo.get_or_create_by_oralsin_id,
            cmd.oralsin_clinic_id,
        )

        # 2) dados externos
        dtos = self._profiled(
            "api.get_inadimplencia",
            self.api.get_inadimplencia,
            InadimplenciaQueryDTO(
                idClinica=cmd.oralsin_clinic_id,
                dataVencimentoInicio=cmd.data_inicio,
                dataVencimentoFim=cmd.data_fim,
            ),
        )
        logger.info("Core Sync: received %d DTOs", len(dtos))

        # 3) persistência em lote
        for idx, dto in enumerate(dtos, 1):
            tag = f"dto{idx}"

            # 3.1 paciente + telefones
            patient = self._profiled(
                f"{tag}.patient", self._persist_patient_and_phones, dto, clinic.id
            )

            # 3.2 contrato
            contract = self._profiled(
                f"{tag}.contract",
                self._persist_contract,
                dto,
                patient.id,
                clinic.id,
            )

            # 3.3 parcelas (bulk seguro)
            self._profiled(
                f"{tag}.installments", self._persist_installments, dto, contract.id
            )
            SYNC_PATIENTS.labels(str(cmd.oralsin_clinic_id)).inc()

        # 4) métricas / profile
        if profiler:
            profiler.disable()
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).sort_stats(
                pstats.SortKey.CUMULATIVE
            ).print_stats(25)
            logger.info("[PROFILE] Core sync stats:\n%s", stream.getvalue())
        SYNC_DURATION.labels(str(cmd.oralsin_clinic_id)).observe(
            time.perf_counter() - start
        )

    # ───────────────────── helpers: paciente & contrato ──────────────────
    def _persist_patient_and_phones(
        self, dto: OralsinPacienteDTO, clinic_id: uuid.UUID
    ):
        patient = self.mapper.map_patient(dto, clinic_id)
        saved = self.patient_repo.save(patient)

        # telefones
        phones = list(self.mapper.map_patient_phones(dto.telefones, saved.id))
        if not phones:
            return saved

        existing = PatientPhoneModel.objects.filter(patient_id=saved.id)
        existing_map = {(p.phone_number, p.phone_type): p for p in existing}

        to_create, to_update = [], []
        for ent in phones:
            key = (ent.phone_number, ent.phone_type)
            model = existing_map.get(key)
            if model:
                if model.phone_number != ent.phone_number or model.phone_type != ent.phone_type:
                    model.phone_number = ent.phone_number
                    model.phone_type = ent.phone_type
                    to_update.append(model)
            else:
                to_create.append(
                    PatientPhoneModel(
                        id=ent.id or uuid.uuid4(),
                        patient_id=saved.id,
                        phone_number=ent.phone_number,
                        phone_type=ent.phone_type,
                    )
                )
        if to_create:
            PatientPhoneModel.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update:
            PatientPhoneModel.objects.bulk_update(to_update, ["phone_number", "phone_type"])
        return saved

    def _persist_contract(
        self,
        dto: OralsinPacienteDTO,
        patient_id: uuid.UUID,
        clinic_id: uuid.UUID,
    ):
        contract = self.mapper.map_contract(dto.contrato, patient_id, clinic_id)
        return self.contract_repo.save(contract)

    # ────────────────────────  ★  PARCELAS  ★  ──────────────────────────
    def _persist_installments( # noqa
        self, dto: OralsinPacienteDTO, contract_id: uuid.UUID
    ) -> None:
        """
        Estratégia bulk:
        1. Mescla payloads → `entities`
        2. Garante **apenas 1** parcela `is_current=True` por (contract_id, contract_version)
        3. Upsert em duas fases:
           3a. bulk_create novos
           3b. bulk_update campos (exceto is_current)
           3c. pós-passo: UPDATE ONE set is_current=True, demais False
        """

        # 0) Map
        entities = self.installment_repo.merge_installments(
            dto.parcelas, dto.contrato, dto.parcelaAtualDetalhe, contract_id
        )
        if not entities:
            return
        
        pm_repo = PaymentMethodRepoImpl()
        for ent in entities:
            if ent.payment_method:
                pm = pm_repo.get_or_create_by_name(ent.payment_method.name)
                ent.payment_method.id = pm.id
                ent.payment_method.oralsin_payment_method_id = (
                    pm.oralsin_payment_method_id
                )

        # 1) Agrupa por (contract_id, contract_version)
        cv_groups: dict[tuple[uuid.UUID, int | None], list] = defaultdict(list)
        for ent in entities:
            cv_groups[(ent.contract_id, ent.contract_version)].append(ent)

        # 2) Normaliza is_current → apenas 1 por grupo
        winners: dict[tuple[uuid.UUID, int | None], int] = {}  # (cid,ver) -> installment_number
        for cv_key, ents in cv_groups.items():
            # Escolhe "favorito": primeiro que já esteja marcado como current,
            # ou a menor due_date
            winner = next((e for e in ents if e.is_current), None)
            if not winner:
                winner = min(ents, key=lambda e: e.due_date)
            winners[cv_key] = winner.installment_number
            for e in ents:
                e.is_current = e.installment_number == winner.installment_number

        # -----------------------------------------------------------------
        # 3) Upsert bulk (ignorando is_current nos UPDATEs)
        keys = {
            (e.contract_id, e.contract_version, e.installment_number) for e in entities
        }
        q = models.Q()
        for cid, ver, num in keys:
            q |= models.Q(
                contract_id=cid, contract_version=ver, installment_number=num
            )
        existing_map = {
            (m.contract_id, m.contract_version, m.installment_number): m
            for m in InstallmentModel.objects.filter(q)
        }

        to_create, to_update = [], []
        UPDATE_FIELDS = [
            "oralsin_installment_id",
            "due_date",
            "installment_amount",
            "received",
            "installment_status",
            "payment_method_id",
            # ← is_current fica fora!  post-step garantirá unicidade
        ]

        def _pm(ent):
            return ent.payment_method.id if ent.payment_method else None

        for ent in entities:
            key = (ent.contract_id, ent.contract_version, ent.installment_number)
            model = existing_map.get(key)
            if model:
                dirty = False
                for f in UPDATE_FIELDS:
                    val = getattr(ent, f) if f != "payment_method_id" else _pm(ent)
                    if getattr(model, f) != val:
                        setattr(model, f, val)
                        dirty = True
                if dirty:
                    to_update.append(model)
            else:
                to_create.append(
                    InstallmentModel(
                        id=ent.id or uuid.uuid4(),
                        contract_id=ent.contract_id,
                        contract_version=ent.contract_version,
                        installment_number=ent.installment_number,
                        oralsin_installment_id=ent.oralsin_installment_id,
                        due_date=ent.due_date,
                        installment_amount=ent.installment_amount,
                        received=ent.received,
                        installment_status=ent.installment_status,
                        payment_method_id=_pm(ent),
                        is_current=ent.is_current,  # insert já com flag certo
                    )
                )

        if to_create:
            InstallmentModel.objects.bulk_create(to_create, ignore_conflicts=True)

        if to_update:
            InstallmentModel.objects.bulk_update(to_update, UPDATE_FIELDS)

        # -----------------------------------------------------------------
        # 4) Pós-passo:  SET is_current=True apenas na parcela vencedora
        #    e force-false em qualquer outra que esteja True
        for (cid, ver), winner_num in winners.items():
            (  # zera competitors
                InstallmentModel.objects.filter(
                    contract_id=cid,
                    contract_version=ver,
                    is_current=True,
                )
                .exclude(installment_number=winner_num)
                .update(is_current=False)
            )
            # garante winner True (caso viesse em to_update sem is_current)
            InstallmentModel.objects.filter(
                contract_id=cid,
                contract_version=ver,
                installment_number=winner_num,
            ).update(is_current=True)
