from __future__ import annotations

import logging
import time
import uuid

from django.db import transaction
from django.utils import timezone

from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.adapters.utils.phone_utils import normalize_phone
from oralsin_core.core.application.commands.sync_commands import SyncInadimplenciaCommand
from oralsin_core.core.application.cqrs import CommandHandler
from oralsin_core.core.application.dtos.oralsin_dtos import (
    InadimplenciaQueryDTO,
    OralsinPacienteDTO,
    OralsinTelefoneDTO,
)
from oralsin_core.core.domain.entities.patient_entity import PatientEntity
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
from oralsin_core.core.domain.repositories.payer_repository import PayerRepository
from oralsin_core.core.domain.services.event_dispatcher import EventDispatcher
from plugins.django_interface.models import (
    ContactSchedule as ContactScheduleModel,
)
from plugins.django_interface.models import PatientPhone as PatientPhoneModel

logger = logging.getLogger(__name__)


class SyncInadimplenciaHandler(CommandHandler[SyncInadimplenciaCommand]):
    """
    Orquestra a sincronização, agora com a nova lógica para
    definir a parcela atual, independente do payload da API.
    """

    def __init__(  # noqa: PLR0913
        self,
        api_client: OralsinAPIClient,
        clinic_repo: ClinicRepository,
        patient_repo: PatientRepository,
        phone_repo: PatientPhoneRepository,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        payer_repo: PayerRepository, 
        mapper: OralsinPayloadMapper,
        dispatcher: EventDispatcher,
    ) -> None:
        self.api = api_client
        self.clinic_repo = clinic_repo
        self.patient_repo = patient_repo
        self.phone_repo = phone_repo
        self.contract_repo = contract_repo
        self.installment_repo = installment_repo
        self.payer_repo = payer_repo
        self.mapper = mapper
        self.dispatcher = dispatcher

    @transaction.atomic
    def handle(self, cmd: SyncInadimplenciaCommand) -> None:
        start_time = time.perf_counter()

        logger.info(f"[SYNC_START] Clínica: {cmd.oralsin_clinic_id}, Resync: {cmd.resync}")
        logger.info(f"[CMD] - {cmd}")
        clinic = self.clinic_repo.get_or_create_by_oralsin_id(cmd.oralsin_clinic_id)
        dtos = self._fetch_dtos(cmd)

        if not dtos:
            logger.info(f"[SYNC_INFO] Nenhum dado de inadimplência encontrado para a clínica {cmd.oralsin_clinic_id}.")
            return

        processed, errors = self._persist_all(dtos, clinic.id, cmd.resync)

        elapsed = time.perf_counter() - start_time
        logger.info(
            f"[SYNC_END] Clínica: {cmd.oralsin_clinic_id}. "
            f"Processados: {processed}, Falhas: {errors}, Duração: {elapsed:.2f}s"
        )

    def _fetch_dtos(self, cmd: SyncInadimplenciaCommand) -> list[OralsinPacienteDTO]:
        logger.info(
            f"[SYNC_QUERY] idClinica: {cmd.oralsin_clinic_id}, dataVencimentoInicio: {cmd.data_inicio}, dataVencimentoFim: {cmd.data_fim}"
        )
        query = InadimplenciaQueryDTO(
            idClinica=cmd.oralsin_clinic_id,
            dataVencimentoInicio=cmd.data_inicio,
            dataVencimentoFim=cmd.data_fim,
        )
        return self.api.get_inadimplencia(query)

    def _persist_all(
        self, dtos: list[OralsinPacienteDTO], clinic_id: uuid.UUID, is_resync: bool
    ) -> tuple[int, int]:
        ok_count, error_count = 0, 0
        for dto in dtos:
            try:
                # 1. Persiste Paciente e Telefones, agora guardando a entidade
                patient_entity = self._persist_patient(dto, clinic_id)
                self._sync_phones(dto.telefones, patient_entity.id)

                # 2. Persiste Contrato
                contract_entity = self._persist_contract(dto, patient_entity.id, clinic_id)
                self._handle_billing_flags(contract_entity.id, dto.contrato.realizarGestaoRecebiveis)

                # 3. Persiste Parcelas, agora passando a entidade do paciente
                self._persist_and_set_current_installment(dto, contract_entity.id, patient_entity)
                
                ok_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"[SYNC_ERROR] Falha ao processar DTO do paciente {dto.idPaciente}: {e}", exc_info=True)

        return ok_count, error_count

    def _persist_patient(self, dto: OralsinPacienteDTO, clinic_id: uuid.UUID) -> PatientEntity:
        # Retorna a entidade completa em vez de apenas o ID
        patient_entity = self.mapper.map_patient(dto, clinic_id)
        return self.patient_repo.save(patient_entity)

    def _sync_phones(self, phones_dto: OralsinTelefoneDTO, patient_id: uuid.UUID) -> None:
        phone_entities = self.mapper.map_patient_phones(phones_dto, patient_id)
        if not phone_entities:
            return

        existing = set(
            PatientPhoneModel.objects
            .filter(patient_id=patient_id)
            .values_list("phone_number", flat=True)
        )

        to_create = []
        seen = set(existing)

        for ent in phone_entities:
            norm = normalize_phone(ent.phone_number, default_region="BR", digits_only=True, with_plus=False)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            to_create.append(
                PatientPhoneModel(
                    id=ent.id,
                    patient_id=patient_id,
                    phone_number=norm,
                    phone_type=ent.phone_type,
                )
            )

        if to_create:
            PatientPhoneModel.objects.bulk_create(to_create, ignore_conflicts=True)

    def _persist_contract(self, dto: OralsinPacienteDTO, patient_id: uuid.UUID, clinic_id: uuid.UUID):
        contract_entity = self.mapper.map_contract(dto.contrato, patient_id, clinic_id)
        return self.contract_repo.save(contract_entity)

    def _handle_billing_flags(self, contract_id: uuid.UUID, should_notify: bool):
        if not should_notify:
            updated_count = ContactScheduleModel.objects.filter(
                contract_id=contract_id, status=ContactScheduleModel.Status.PENDING
            ).update(status='cancelled', updated_at=timezone.now())
            if updated_count > 0:
                logger.info(f"[SYNC_FLAGS] {updated_count} agendamentos cancelados para o contrato {contract_id}.")

    def _persist_and_set_current_installment(self, dto: OralsinPacienteDTO, contract_id: uuid.UUID, patient_entity: PatientEntity):
        """
        Salva as parcelas e define a 'is_current' baseado na nova regra.
        """
        # 1. Mapeia e salva todas as parcelas, passando a entidade do paciente
        installment_entities = self.mapper.map_installments(
            dto.parcelas,
            dto.contrato.versaoContrato,
            contract_id,
            patient_entity 
        )
        
        # Adiciona a persistência dos pagadores antes de salvar as parcelas
        for inst_entity in installment_entities:
            payer_entity = self.payer_repo.upsert(inst_entity.payer)
            inst_entity.payer.id = payer_entity.id

        self.installment_repo.save_many(installment_entities)

        # 2. Define a parcela atual
        self.installment_repo.set_current_installment_atomically(
            contract_id=contract_id,
            oralsin_installment_id=None
        )
        
        # 3. Calcula e grava parcelas restantes
        remaining = self.installment_repo.count_remaining_from_current(contract_id)
        self.contract_repo.set_remaining_installments(contract_id, remaining)