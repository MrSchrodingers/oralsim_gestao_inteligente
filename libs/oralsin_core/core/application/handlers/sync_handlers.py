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
from oralsin_core.adapters.observability.metrics import SYNC_DURATION, SYNC_PATIENTS, SYNC_RUNS
from oralsin_core.core.application.commands.sync_commands import SyncInadimplenciaCommand
from oralsin_core.core.application.cqrs import CommandHandler
from oralsin_core.core.application.dtos.oralsin_dtos import InadimplenciaQueryDTO, OralsinPacienteDTO
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_phone_repository import PatientPhoneRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from oralsin_core.core.domain.services.event_dispatcher import EventDispatcher
from plugins.django_interface.models import (
    Installment as InstallmentModel,
)
from plugins.django_interface.models import (
    PatientPhone as PatientPhoneModel,
)

logger = logging.getLogger(__name__)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s [%(funcName)s:%(lineno)d]'
    ))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

PROFILE_ENABLED = os.getenv('PROFILE_SYNC_HANDLER', 'false').lower() == 'true'


class SyncInadimplenciaHandler(CommandHandler[SyncInadimplenciaCommand]):
    """
    Sync de inadimplência no core: persiste pacientes, contratos e parcelas.
    Não realiza nenhum agendamento ou notificação.
    """
    def __init__( # noqa
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

    def _profiled(self, name: str, fn, *args, **kwargs) -> Any:
        if not PROFILE_ENABLED:
            return fn(*args, **kwargs)
        start = time.perf_counter()
        before = len(connection.queries) if settings.DEBUG else 0
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - start
        after = len(connection.queries) if settings.DEBUG else 0
        delta = after - before if settings.DEBUG else 'N/A'
        logger.info(f"[PROFILE] {name}: {elapsed:.3f}s, ΔQ={delta}")
        return result

    @transaction.atomic
    def handle(self, cmd: SyncInadimplenciaCommand) -> None:
        profiler = cProfile.Profile() if PROFILE_ENABLED else None
        if profiler:
            profiler.enable()
        SYNC_RUNS.labels(str(cmd.oralsin_clinic_id)).inc()
        start = time.perf_counter()
        
        # 1) registrar clínica
        clinic = self._profiled(
            "clinic.get_or_create",
            self.clinic_repo.get_or_create_by_oralsin_id,
            cmd.oralsin_clinic_id
        )

        # 2) obter dados externos
        dtos = self._profiled(
            "api.get_inadimplencia",
            self.api.get_inadimplencia,
            InadimplenciaQueryDTO(
                idClinica=cmd.oralsin_clinic_id,
                dataVencimentoInicio=cmd.data_inicio,
                dataVencimentoFim=cmd.data_fim,
            )
        )
        logger.info(f"Core Sync: received {len(dtos)} DTOs")

        # 3) persistir entidades do core
        for idx, dto in enumerate(dtos, 1):
            tag = f"dto{idx}"

            # 3.1 Persistir paciente, receber UUID real
            saved_patient = self._profiled(f"{tag}.patient", self._persist_patient_and_phones, dto, clinic.id)

            # 3.2 Persistir contrato usando UUID real do paciente
            saved_contract = self._profiled(f"{tag}.contract", self._persist_contract, dto, saved_patient.id, clinic.id)

            # 3.3 Persistir parcelas
            self._profiled(f"{tag}.installments", self._persist_installments, dto, saved_contract.id)
            SYNC_PATIENTS.labels(str(cmd.oralsin_clinic_id)).inc()

        if profiler:
            profiler.disable()
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream).sort_stats(pstats.SortKey.CUMULATIVE)
            stats.print_stats(20)
            logger.info(f"[PROFILE] Core sync stats:\n{stream.getvalue()}")
        SYNC_DURATION.labels(str(cmd.oralsin_clinic_id)).observe(time.perf_counter() - start)

    def _persist_patient_and_phones(self, dto: OralsinPacienteDTO, clinic_id: uuid.UUID):
        patient = self.mapper.map_patient(dto, clinic_id)
        saved = self.patient_repo.save(patient)

        phones = list(self.mapper.map_patient_phones(dto.telefones, saved.id))
        if phones:
            existing = PatientPhoneModel.objects.filter(patient_id=saved.id)
            existing_map = {(p.phone_number, p.phone_type): p for p in existing}
            to_create, to_update = [], []
            for ent in phones:
                key = (ent.phone_number, ent.phone_type)
                model = existing_map.get(key)
                if model:
                    updated = False
                    if model.phone_number != ent.phone_number:
                        model.phone_number = ent.phone_number
                        updated = True
                    if model.phone_type != ent.phone_type:
                        model.phone_type = ent.phone_type
                        updated = True
                    if updated:
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
                PatientPhoneModel.objects.bulk_update(to_update, ['phone_number', 'phone_type'])
        return saved

    def _persist_contract(
        self, dto: OralsinPacienteDTO, patient_id: uuid.UUID, clinic_id: uuid.UUID
    ):
        contract = self.mapper.map_contract(dto.contrato, patient_id, clinic_id)
        return self.contract_repo.save(contract)

    def _persist_installments(
        self, dto: OralsinPacienteDTO, contract_id: uuid.UUID
    ) -> None:
        entities = self.installment_repo.merge_installments(
            dto.parcelas, dto.parcelaAtualDetalhe, contract_id
        )
        if not entities:
            return

        # Bulk upsert pattern
        from django.db import models
        keys = {(e.contract_id, e.contract_version, e.installment_number) for e in entities}
        q = models.Q()
        for cid, ver, num in keys:
            q |= models.Q(contract_id=cid, contract_version=ver, installment_number=num)
        existing = {
            (i.contract_id, i.contract_version, i.installment_number): i
            for i in InstallmentModel.objects.filter(q)
        }

        to_create, to_update = [], []
        update_fields = [
            'oralsin_installment_id', 'due_date', 'installment_amount',
            'received', 'installment_status', 'payment_method_id', 'is_current',
        ]
        for ent in entities:
            key = (ent.contract_id, ent.contract_version, ent.installment_number)
            model = existing.get(key)
            if model:
                changed = False
                for f in update_fields:
                    val = getattr(ent, f) if f != 'payment_method_id' else (
                        ent.payment_method.id if ent.payment_method else None
                    )
                    if getattr(model, f) != val:
                        setattr(model, f, val)
                        changed = True
                if changed:
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
                        payment_method_id=ent.payment_method.id if ent.payment_method else None,
                        is_current=ent.is_current,
                    )
                )
        if to_create:
            InstallmentModel.objects.bulk_create(to_create)
        if to_update:
            InstallmentModel.objects.bulk_update(to_update, update_fields)
