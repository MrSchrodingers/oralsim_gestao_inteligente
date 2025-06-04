from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from asgiref.sync import sync_to_async
from django.utils import timezone
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from structlog import get_logger

from cordial_billing.core.application.commands.collect_commands import (
    SyncOldDebtsCommand,
)
from cordial_billing.core.domain.entities.collection_case_entity import (
    CollectionCaseEntity,
)
from cordial_billing.core.domain.events.events import DebtEscalatedEvent
from cordial_billing.core.domain.repositories.collection_case_repository import CollectionCaseRepository
from cordial_billing.core.domain.repositories.deal_repository import DealRepository
from notification_billing.core.application.cqrs import CommandHandler, PagedResult


class SyncOldDebtsHandler(CommandHandler[SyncOldDebtsCommand]):
    """
    Cria **apenas um** `CollectionCase` por paciente que tenha
    qualquer parcela vencida há >= min_days, mesmo que sejam várias.
    """

    def __init__(  # noqa: PLR0913
        self,
        installment_repo: InstallmentRepository,  # ← oralsin_core
        patient_repo: PatientRepository,          # ← oralsin_core
        deal_repo: DealRepository,
        case_repo: CollectionCaseRepository,
        contract_repo: ContractRepository,
        dispatcher,
        logger=None,
    ):
        self.installment_repo = installment_repo
        self.patient_repo = patient_repo
        self.deal_repo = deal_repo
        self.case_repo = case_repo
        self.contract_repo = contract_repo
        self.dispatcher = dispatcher
        self.log = logger or get_logger(__name__)

    # ----------------------------------------------------------------- #
    async def handle(self, cmd: SyncOldDebtsCommand) -> dict[str, int]:
        created, skipped = 0, 0

        # 1. pega todos os contratos da clínica
        contracts = await sync_to_async(self.contract_repo.list_by_clinic)(cmd.clinic_id)

        self.log.info(
            "sync_old_debts_started",
            clinic_id=cmd.clinic_id,
            contracts=len(contracts),
            min_days_overdue=cmd.min_days,
        )

        # set para rastrear quais pacientes já receberam CollectionCase
        processed_patients: set[str] = set()

        for contract in contracts:
            page = 0

            while True:
                # 2. busca parcelas vencidas (ORM síncrono → sync_to_async)
                overdue_page: PagedResult[Any] = await sync_to_async(
                    self.installment_repo.list_current_overdue
                )(
                    contract_id=contract.id,
                    min_days_overdue=cmd.min_days,
                    offset=page * 1000,
                    limit=1000,
                )

                self.log.info(
                    "sync_old_debts_page",
                    clinic_id=cmd.clinic_id,
                    contract_id=contract.id,
                    page=page,
                    total_pages=overdue_page.total_pages,
                    total=overdue_page.total,
                )

                if not overdue_page.items:
                    break

                for inst in overdue_page.items:
                    # 3. Se já existe case para essa parcele, pula
                    exists_case = await sync_to_async(
                        self.case_repo.exists_for_installment
                    )(inst.id)
                    if exists_case:
                        skipped += 1
                        continue

                    # 4. obtém patient_id via contrato
                    patient_id = contract.patient_id

                    # 5. se esse paciente já teve um case criado, pula
                    if patient_id in processed_patients:
                        skipped += 1
                        continue

                    # 6. busca paciente e deal de forma assíncrona
                    patient = await sync_to_async(self.patient_repo.find_by_id)(patient_id)
                    deal = None
                    if patient and patient.cpf:
                        deal = await self.deal_repo.find_by_cpf(patient.cpf)
                        
                    # 7. cria CollectionCaseEntity para esse paciente (primeira parcela 90+)
                    case = CollectionCaseEntity(
                        id=uuid4(),
                        patient_id=patient_id,
                        contract_id=inst.contract_id,
                        installment_id=inst.id,
                        clinic_id=contract.clinic_id,
                        opened_at=timezone.now(),
                        amount=Decimal(inst.installment_amount),
                        deal_id=deal.id if deal else None,
                        status="open",
                    )

                    # 8. salva no repositório
                    await sync_to_async(self.case_repo.save)(case)
                    created += 1
                    processed_patients.add(patient_id)

                    # 9. dispara evento
                    self.dispatcher.dispatch(DebtEscalatedEvent(case_id=case.id))

                page += 1

        self.log.info(
            "sync_old_debts_finished",
            clinic_id=cmd.clinic_id,
            created=created,
            skipped=skipped,
        )
        return {"created": created, "skipped": skipped}
