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
from typing import Any

from django.conf import settings
from django.db import connection, transaction

from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.adapters.observability.metrics import (
    SYNC_DURATION,
    SYNC_PATIENTS,
    SYNC_RUNS,
)
from oralsin_core.core.application.commands.register_commands import ResyncClinicCommand
from oralsin_core.core.application.commands.sync_commands import SyncInadimplenciaCommand
from oralsin_core.core.application.cqrs import CommandHandler
from oralsin_core.core.application.dtos.oralsin_dtos import (
    InadimplenciaQueryDTO,
    OralsinPacienteDTO,
)
from oralsin_core.core.application.services.oralsin_sync_service import OralsinSyncService
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
        self.is_resync = cmd.resync
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

            # 3.1 paciente + telefones ----------------------------------------
            patient = self._profiled(
                f"{tag}.patient", self._persist_patient_and_phones, dto, clinic.id
            )
            if patient is None:                       # ← NEW
                continue                              # nada a atualizar

            # 3.2 contrato -----------------------------------------------------
            contract = self._profiled(
                f"{tag}.contract",
                self._persist_contract,
                dto,
                patient.id,
                clinic.id,
            )
            if contract is None:                      # ← NEW
                continue

            # 3.3 parcelas -----------------------------------------------------
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
        """
        • full-sync  → UPSERT completo (create + update)
        • resync     → 
            – se paciente existir → UPDATE
            – se for novo:
                · cria somente se DTO tiver dados essenciais
                · senão, ignora
        """
        is_resync = getattr(self, "is_resync", False)

        # --------- regra de “DTO completo” ----------
        def _dto_is_complete(d: OralsinPacienteDTO) -> bool:
            """
            Retorna True se há dados suficientes para criarmos um novo paciente
            durante o *resync*.

            • Usa getattr para evitar AttributeError se o campo não existir.
            • Você pode ajustar os requisitos à vontade.
            """
            nome_ok  = getattr(d, "nomePaciente", None)
            telef_ok = bool(getattr(d, "telefones", []))          # ≥1 tel
            contr_ok = getattr(d, "contrato", None) is not None

            # Campos opcionais – checamos se EXISTEM, mas não são mandatórios
            _cpf_ok   = getattr(d, "cpf", None) or getattr(d, "cpfPaciente", None)
            _email_ok = getattr(d, "email", None) or getattr(d, "emailPaciente", None)

            return nome_ok and telef_ok and contr_ok  #  ← regras mínimas

        # --------- Paciente ---------
        patient_ent = self.mapper.map_patient(dto, clinic_id)

        if is_resync:
            if self.patient_repo.exists(dto.idPaciente):
                saved = self.patient_repo.update(patient_ent)
            elif _dto_is_complete(dto):
                saved = self.patient_repo.save(patient_ent)           # cria
                logger.debug(
                    "Resync: paciente %s criado (DTO completo).", dto.idPaciente
                )
            else:
                logger.debug(
                    "Resync: paciente %s ignorado (DTO incompleto).", dto.idPaciente
                )
                return None
        else:  # full-sync
            saved = self.patient_repo.save(patient_ent)

        # --------- Telefones ---------
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
                    model.phone_type   = ent.phone_type
                    to_update.append(model)
            elif not is_resync or (is_resync and saved):      # pode criar telefone novo
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
        is_resync = getattr(self, "is_resync", False)
        contract_ent = self.mapper.map_contract(dto.contrato, patient_id, clinic_id)

        if is_resync:
            if not self.contract_repo.exists(dto.contrato.idContrato):
                logger.debug("Resync: contrato %s inexistente – ignorado",
                            dto.contrato.idContrato)
                return None
            return self.contract_repo.update(contract_ent)
        return self.contract_repo.save(contract_ent)

    # ───────────────── ★ PARCELAS (Estrita) ★ ──────────────────
    def _persist_installments(self, dto, contract_id):
        entities = self.mapper.map_installments(
            parcelas=dto.parcelas,
            contrato_version=dto.contrato.versaoContrato,
            contract_id=contract_id,
        )

        # ① Se estamos em resync → só lida com parcelas já existentes
        if getattr(self, "is_resync", False):
            existing = self.installment_repo.existing_oralsin_ids(
                [e.oralsin_installment_id for e in entities]
            )
            entities = [e for e in entities if e.oralsin_installment_id in existing]

        if not entities:
            return

        # ② Decide quem é a “current”
        current_id = (
            dto.parcelaAtualDetalhe.idContratoParcela
            if dto.parcelaAtualDetalhe else None
        )
        for e in entities:
            e.is_current = False                # zera tudo na 1ª fase

        # ③ Primeira fase – atualiza valores + is_current=False
        self.installment_repo.save_many(entities)

        # ④ Segunda fase – seta exatamente uma current
        if current_id:
            self.installment_repo.set_current_installment_atomically(
                contract_id=contract_id,
                oralsin_installment_id=current_id,
            )
                
                
class ResyncClinicHandler(CommandHandler[ResyncClinicCommand]):
    """
    Executa o *delta sync* diário.  
    Ele simplesmente delega para `OralsinSyncService.full_sync(...)`
    com uma janela curta de datas para capturar *updates*.
    """

    def __init__(
        self,
        sync_service: OralsinSyncService,
        clinic_repo: ClinicRepository,
    ) -> None:
        self.sync_service = sync_service
        self.clinic_repo  = clinic_repo

    # ------------------------------------------------------------------
    def handle(self, cmd: ResyncClinicCommand) -> None:
        clinic = self.clinic_repo.find_by_oralsin_id(cmd.oralsin_clinic_id)
        if not clinic:
            raise ValueError(
                f"Clinic with OralsinID={cmd.oralsin_clinic_id} not found."
            )

        logger.info(
            "⏩ [Resync] %s  %s → %s",
            cmd.oralsin_clinic_id,
            cmd.initial_date.isoformat(),
            cmd.final_date.isoformat(),
        )

        # delega; já temos toda a lógica no serviço
        self.sync_service.full_sync(
            clinic_id   = cmd.oralsin_clinic_id,
            data_inicio = cmd.initial_date,
            data_fim    = cmd.final_date,
            no_schedules= cmd.no_schedules,
            resync      = True,  
        )