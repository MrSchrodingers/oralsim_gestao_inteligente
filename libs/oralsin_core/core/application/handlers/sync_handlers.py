# ——————————————————————————————————————————————————————————
#  SyncInadimplenciaHandler – v2 (robusta, bulk-safe)
#  · Mantém alta performance em bulk_create/bulk_update
#  · Garante **UMA** parcela is_current=True por (contract_id, contract_version)
#  · Evita violar UNIQUE CONSTRAINT `unique_current_per_contract_version`
#  · Melhora rastreabilidade com logs estruturados + timings
# ——————————————————————————————————————————————————————————
from __future__ import annotations

import cProfile
import io
import logging
import os
import pstats
import time
import uuid
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, TypeVar

from django.conf import settings
from django.core.management import call_command
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

# ─────────────────────────────── logger ────────────────────────────────
logger = logging.getLogger("sync_inadimplencia")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "%(message)s [%(funcName)s:%(lineno)d]"
        )
    )
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

PROFILE_ENABLED = os.getenv("PROFILE_SYNC_HANDLER", "true").lower() == "true"

_T = TypeVar("_T")


def profiled(
    label: str,
    *,
    context: Mapping[str, Any] | None = None,
) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """
    Decorador interno p/ medir tempo de execução e, em DEBUG, nº de queries.
    Uso:
        @profiled("repo.save", context={"id": obj.id})
        def fn(...):
            ...
    """
    def decorator(fn: Callable[..., _T]) -> Callable[..., _T]:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> _T:
            if not PROFILE_ENABLED:
                return fn(*args, **kwargs)

            q_before = len(connection.queries) if settings.DEBUG else 0
            start = time.perf_counter()

            result = fn(*args, **kwargs)

            elapsed = time.perf_counter() - start
            q_after = len(connection.queries) if settings.DEBUG else 0

            meta = ", ".join(f"{k}={v}" for k, v in (context or {}).items())
            logger.info(
                "[PROFILE] %s%s – %.3fs, ΔQ=%s",
                label,
                f" [{meta}]" if meta else "",
                elapsed,
                (q_after - q_before) if settings.DEBUG else "n/a",
            )
            return result

        return wrapper

    return decorator


# ────────────────────────────  Handler  ────────────────────────────────
class SyncInadimplenciaHandler(CommandHandler[SyncInadimplenciaCommand]):
    """
    Sincroniza inadimplência: pacientes, contratos e parcelas.
    NÃO dispara agendamentos ou notificações.
    """

    # ───────── ctor: injeta dependências explícitas ─────────
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

    # ─────────── handle (transacional) ────────────
    @transaction.atomic
    def handle(self, cmd: SyncInadimplenciaCommand) -> None:
        profiler = cProfile.Profile() if PROFILE_ENABLED else None
        if profiler:
            profiler.enable()

        SYNC_RUNS.labels(str(cmd.oralsin_clinic_id)).inc()
        overall_start = time.perf_counter()

        logger.info(
            "▶️  Iniciando sync inadimplência "
            "clinic=%s resync=%s window=%s→%s",
            cmd.oralsin_clinic_id,
            cmd.resync,
            cmd.data_inicio,
            cmd.data_fim,
        )

        # 1) Clínica
        clinic = self._get_or_create_clinic(cmd.oralsin_clinic_id)

        # 2) DTOs de inadimplência
        dtos = self._fetch_dtos(cmd)
        logger.info("📦  %d DTOs recebidos da API", len(dtos))

        # 3) Persistência principal
        processed, errors = self._persist_all(dtos, clinic.id, cmd.resync)
        logger.info("✅  %d DTOs processados com sucesso, %d falharam", processed, errors)

        # 4) Métricas & profile
        elapsed = time.perf_counter() - overall_start
        SYNC_DURATION.labels(str(cmd.oralsin_clinic_id)).observe(elapsed)

        if profiler:
            profiler.disable()
            s = io.StringIO()
            pstats.Stats(profiler, stream=s).sort_stats(
                pstats.SortKey.CUMULATIVE
            ).print_stats(25)
            logger.info("[PROFILE] Estatísticas detalhadas:\n%s", s.getvalue())

        logger.info("⏹️  Sync concluído em %.2fs", elapsed)

    # ────────────────────  Fases da sync  ─────────────────────
    # 1) Clínica
    @profiled("clinic.get_or_create")
    def _get_or_create_clinic(self, oralsin_id: int):
        return self.clinic_repo.get_or_create_by_oralsin_id(oralsin_id)

    # 2) Chamada externa
    @profiled("api.get_inadimplencia")
    def _fetch_dtos(self, cmd: SyncInadimplenciaCommand) -> list[OralsinPacienteDTO]:
        return self.api.get_inadimplencia(
            InadimplenciaQueryDTO(
                idClinica=cmd.oralsin_clinic_id,
                dataVencimentoInicio=cmd.data_inicio,
                dataVencimentoFim=cmd.data_fim,
            )
        )

    # 3) Loop principal
    def _persist_all(
        self,
        dtos: list[OralsinPacienteDTO],
        clinic_id: uuid.UUID,
        is_resync: bool,
    ) -> tuple[int, int]:
        ok, failed = 0, 0
        # Agrupamos exceções para reportar depois, mas continuamos o loop
        for idx, dto in enumerate(dtos, 1):
            tag = f"dto{idx}"
            try:
                patient = self._persist_patient(dto, clinic_id, is_resync, tag)
                if not patient:
                    continue  # Resync ignorado (DTO incompleto ou paciente ausente)

                contract = self._persist_contract(dto, patient, clinic_id, is_resync, tag)
                if not contract:
                    continue  # Resync ignorado (contrato ausente)

                self._persist_installments(dto, contract.id, is_resync, tag)
                SYNC_PATIENTS.labels(str(clinic_id)).inc()
                ok += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.exception(
                    "❌  Falha ao processar DTO %s "
                    "(patient=%s contract=%s): %s",
                    tag,
                    dto.idPaciente,
                    dto.contrato.idContrato,
                    exc,
                )
        return ok, failed

    # ──────────────── Persistência – Paciente ────────────────
    def _persist_patient(
        self,
        dto: OralsinPacienteDTO,
        clinic_id: uuid.UUID,
        is_resync: bool,
        tag: str,
    ):
        ctx = {"patient_id": dto.idPaciente, "tag": tag}

        @profiled("patient.save", context=ctx)
        def _save() -> uuid.UUID | None:
            # Regras de DTO completo (para criar paciente novo em resync)
            def _dto_complete(d: OralsinPacienteDTO) -> bool:
                has_name = bool(getattr(d, "nomePaciente", None))
                has_phone = bool(getattr(d, "telefones", []))
                has_contract = d.contrato is not None
                return has_name and has_phone and has_contract

            patient_ent = self.mapper.map_patient(dto, clinic_id)

            if is_resync and self.patient_repo.exists(dto.idPaciente):
                return self.patient_repo.update(patient_ent).id

            if is_resync and not _dto_complete(dto):
                logger.debug("Resync: paciente %s ignorado (DTO incompleto)", dto.idPaciente)
                return None

            # full-sync ou resync + completo
            return self.patient_repo.save(patient_ent).id

        patient_id = _save()
        if patient_id is None:
            return None

        # Telefones
        self._sync_phones(dto.telefones, patient_id, is_resync, tag)
        return patient_id  # simples uuid para acelerar GC

    # Telefones em lote
    def _sync_phones(
        self,
        phones_dto: list[dict[str, Any]],
        patient_id: uuid.UUID,
        is_resync: bool,
        tag: str,
    ) -> None:
        ctx = {"patient_id": patient_id, "tag": tag}

        @profiled("phones.sync", context=ctx)
        def _impl() -> None:
            entities = list(self.mapper.map_patient_phones(phones_dto, patient_id))
            if not entities:
                return

            existing = PatientPhoneModel.objects.filter(patient_id=patient_id)
            existing_map = {(p.phone_number, p.phone_type): p for p in existing}

            to_create: list[PatientPhoneModel] = []
            to_update: list[PatientPhoneModel] = []

            for ent in entities:
                key = (ent.phone_number, ent.phone_type)
                model = existing_map.get(key)

                if model:
                    # Comparação direta garante update só quando necessário
                    if model.phone_number != ent.phone_number or model.phone_type != ent.phone_type:
                        model.phone_number = ent.phone_number
                        model.phone_type = ent.phone_type
                        to_update.append(model)
                elif not is_resync or (is_resync and patient_id):
                    to_create.append(
                        PatientPhoneModel(
                            id=ent.id or uuid.uuid4(),
                            patient_id=patient_id,
                            phone_number=ent.phone_number,
                            phone_type=ent.phone_type,
                        )
                    )

            if to_create:
                PatientPhoneModel.objects.bulk_create(to_create, ignore_conflicts=True)
                logger.debug("📞  %d telefones criados (patient=%s)", len(to_create), patient_id)
            if to_update:
                PatientPhoneModel.objects.bulk_update(
                    to_update, ["phone_number", "phone_type"]
                )
                logger.debug("📞  %d telefones atualizados (patient=%s)", len(to_update), patient_id)

        _impl()

    # ──────────────── Persistência – Contrato ────────────────
    def _persist_contract(
        self,
        dto: OralsinPacienteDTO,
        patient_id: uuid.UUID,
        clinic_id: uuid.UUID,
        is_resync: bool,
        tag: str,
    ):
        ctx = {
            "patient_id": patient_id,
            "contract_id": dto.contrato.idContrato,
            "tag": tag,
        }

        @profiled("contract.save", context=ctx)
        def _save():
            contract_ent = self.mapper.map_contract(dto.contrato, patient_id, clinic_id)

            if is_resync and not self.contract_repo.exists(
                dto.contrato.idContrato,
                contract_version=dto.contrato.versaoContrato,
                patient_id=patient_id,
            ):
                logger.debug(
                    "Resync: contrato %s inexistente p/ paciente %s – ignorado",
                    dto.contrato.idContrato,
                    patient_id,
                )
                return None

            return (
                self.contract_repo.update(contract_ent)
                if is_resync
                else self.contract_repo.save(contract_ent)
            )

        return _save()

    # ─────────────── Persistência – Parcelas ────────────────
    def _persist_installments(
        self,
        dto: OralsinPacienteDTO,
        contract_id: uuid.UUID,
        is_resync: bool,
        tag: str,
    ) -> None:
        ctx = {"contract_id": contract_id, "tag": tag}

        @profiled("installments.sync", context=ctx)
        def _impl():
            entities = self.mapper.map_installments(
                parcelas=dto.parcelas,
                contrato_version=dto.contrato.versaoContrato,
                contract_id=contract_id,
            )

            if is_resync:
                existing_ids = self.installment_repo.existing_oralsin_ids(
                    [e.oralsin_installment_id for e in entities]
                )
                entities = [e for e in entities if e.oralsin_installment_id in existing_ids]
                if not entities:
                    return

            # (i) apenas grava/atualiza em lote
            self.installment_repo.save_many(entities)

            # (ii) **só depois** garante que exista exatamente 1 parcela atual
            current_id = (
                dto.parcelaAtualDetalhe.idContratoParcela
                if dto.parcelaAtualDetalhe else None
            )
            if current_id:
                self.installment_repo.set_current_installment_atomically(
                    contract_id=contract_id,
                    oralsin_installment_id=current_id,
                )

        _impl()

# ——————————————————————————————————————————————————————————
#  ResyncClinicHandler – sem alterações lógicas, apenas logs
# ——————————————————————————————————————————————————————————
class ResyncClinicHandler(CommandHandler[ResyncClinicCommand]):
    """
    Executa o *delta sync* diário.  
    Ele delega para `seed_data` (ali residem as regras completas).
    """

    def __init__(self, clinic_repo: ClinicRepository) -> None:
        self.clinic_repo = clinic_repo

    @profiled("clinic.resync_handle")
    def handle(self, cmd: ResyncClinicCommand) -> None:
        clinic = self.clinic_repo.find_by_oralsin_id(cmd.oralsin_clinic_id)
        if not clinic:
            raise ValueError(f"Clinic with OralsinID={cmd.oralsin_clinic_id} not found.")

        logger.info(
            "🔄  Resync solicitado clinic=%s window=%s→%s no_schedules=%s",
            cmd.oralsin_clinic_id,
            cmd.initial_date,
            cmd.final_date,
            cmd.no_schedules,
        )

        window_days = max((cmd.final_date - cmd.initial_date).days, 1)
        call_command(
            "seed_data",
            clinic_name=clinic.name,
            owner_name=clinic.owner_name or clinic.name,
            skip_admin=True,
            skip_clinic_user=True,
            no_schedules=cmd.no_schedules,
            resync=True,
            window_days=window_days,
            initial_date=cmd.initial_date.isoformat(),
            final_date=cmd.final_date.isoformat(),
        )
        logger.info("✅  Resync concluído clinic=%s", cmd.oralsin_clinic_id)
