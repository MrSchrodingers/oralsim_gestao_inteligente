from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import uuid4

from asgiref.sync import sync_to_async
from django.utils import timezone
from oralsin_core.core.domain.repositories.billing_settings_repository import BillingSettingsRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.covered_clinic_repository import CoveredClinicRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from structlog import get_logger

from cordial_billing.core.application.commands.collect_commands import SyncOldDebtsCommand
from cordial_billing.core.domain.entities.collection_case_entity import CollectionCaseEntity
from cordial_billing.core.domain.events.events import DebtEscalatedEvent
from cordial_billing.core.domain.repositories.collection_case_repository import CollectionCaseRepository
from cordial_billing.core.domain.repositories.deal_repository import DealRepository
from notification_billing.core.application.cqrs import CommandHandler, PagedResult


class SyncOldDebtsHandler(CommandHandler[SyncOldDebtsCommand]):
    """
    Cria **apenas um** `CollectionCase` por paciente que tenha
    qualquer parcela vencida há >= min_days_overdue configurado em BillingSettings.
    """

    def __init__(  # noqa: PLR0913
        self,
        installment_repo: InstallmentRepository,
        patient_repo: PatientRepository,
        deal_repo: DealRepository,
        case_repo: CollectionCaseRepository,
        contract_repo: ContractRepository,
        billing_settings_repo: BillingSettingsRepository,
        covered_clinic_repo: CoveredClinicRepository,
        dispatcher,
        logger=None,
    ):
        self.installment_repo = installment_repo
        self.patient_repo = patient_repo
        self.deal_repo = deal_repo
        self.case_repo = case_repo
        self.contract_repo = contract_repo
        self.billing_settings_repo = billing_settings_repo
        self.covered_clinic_repo = covered_clinic_repo
        self.dispatcher = dispatcher
        self.log = logger or get_logger(__name__)

    # ----------------------------------------------------------------- #
    async def handle(self, cmd: SyncOldDebtsCommand) -> dict[str, int]:  # noqa: PLR0912
        created, skipped = 0, 0
        skipped_no_deal_and_created_case = 0  
        skipped_existing_case_with_deal = 0   
        skipped_existing_case_without_deal = 0  

        covered = await sync_to_async(self.covered_clinic_repo.find_by_api_id)(cmd.clinic_id)
        if not covered:
            raise ValueError(f"Oralsin clinic {cmd.clinic_id} não mapeada em CoveredClinic")
        clinic_uuid = covered.clinic_id

        settings = await sync_to_async(self.billing_settings_repo.get)(clinic_uuid)
        min_days = settings.min_days_overdue
        self.log.info("using_billing_settings", clinic_id=cmd.clinic_id, min_days_overdue=min_days)

        contracts = await sync_to_async(self.contract_repo.list_by_clinic)(clinic_uuid)

        self.log.info(
            "sync_old_debts_started",
            clinic_id=cmd.clinic_id,
            contracts=len(contracts),
            min_days_overdue=min_days,
        )

        processed_patients: set[str] = set()

        for contract in contracts:
            if not contract.do_billings:
                continue

            page = 0
            while True:
                overdue_page: PagedResult[Any] = await sync_to_async(self.installment_repo.list_current_overdue)(
                    contract_id=contract.id,
                    min_days_overdue=min_days,
                    offset=page * 1000,
                    limit=1000,
                )
                if not overdue_page.items:
                    break

                for inst in overdue_page.items:
                    patient_id = contract.patient_id

                    # 🔒 permitir apenas 1 case por paciente por execução:
                    if patient_id in processed_patients:
                        continue

                    # Tenta localizar um case existente
                    case = await sync_to_async(self.case_repo.find_by_installment_id)(inst.id)

                    # Se já existe e já tem deal, ignore
                    if case and case.deal_id:
                        skipped += 1
                        skipped_existing_case_with_deal += 1
                        continue

                    # Busca paciente e deal por CPF
                    patient = await sync_to_async(self.patient_repo.find_by_id)(patient_id)
                    deal = None
                    if patient and patient.cpf:
                        # Normalizar CPF no repositório de deal é responsabilidade do repo
                        deal = await self.deal_repo.find_by_cpf(patient.cpf)

                    created_now = False

                    # Se o case não existe ainda, crie-o (mesmo sem deal)
                    if not case:
                        case = CollectionCaseEntity(
                            id=uuid4(),
                            patient_id=patient_id,
                            contract_id=inst.contract_id,
                            installment_id=inst.id,
                            clinic_id=contract.clinic_id,
                            opened_at=timezone.now(),
                            amount=Decimal(inst.installment_amount),
                            status="open",
                            deal_sync_status="pending",
                            deal_id=None,
                            stage_id=None,
                            last_stage_id=None,
                        )
                        created += 1
                        created_now = True

                    # Se achou deal, vincule
                    if deal:
                        case = replace(case, deal_id=deal.id, stage_id=getattr(deal, "stage_id", None))
                        
                    # Não achou deal: mantém deal_id=None, apenas registra diagnóstico
                    elif not created_now:
                        # já existia o case e segue sem deal
                        skipped_existing_case_without_deal += 1
                    else:
                        # criado agora, sem deal ainda
                        skipped_no_deal_and_created_case += 1

                    # Persiste (tanto criação quanto atualização)
                    await sync_to_async(self.case_repo.save)(case)

                    # Dispara evento somente para criação naquela iteração
                    if created_now:
                        self.dispatcher.dispatch(DebtEscalatedEvent(case_id=case.id))

                    processed_patients.add(patient_id)

                page += 1

        self.log.info(
            "sync_old_debts_finished",
            clinic_id=cmd.clinic_id,
            created=created,
            skipped=skipped,
            diag_skipped_existing_case_with_deal=skipped_existing_case_with_deal,
            diag_skipped_existing_case_without_deal=skipped_existing_case_without_deal,
            diag_created_without_deal_pending=skipped_no_deal_and_created_case,
        )
        return {"created": created, "skipped": skipped}