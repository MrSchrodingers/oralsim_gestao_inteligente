from __future__ import annotations

from asgiref.sync import sync_to_async
from django.db.models import Prefetch
from structlog import get_logger

from cordial_billing.core.application.commands.create_deal_command import (
    CreatePipedriveDealCommand,
)
from cordial_billing.core.application.services.pipedrive_deal_payload_builder import (
    PipedriveDealPayloadBuilder,
)
from cordial_billing.core.application.services.pipedrive_sync_service import (
    PipedriveSyncService,
)
from notification_billing.core.application.cqrs import CommandHandler
from plugins.django_interface.models import ClinicPhone, CollectionCase, Installment, PatientPhone

log = get_logger(__name__)


class CreatePipedriveDealHandler(
    CommandHandler[CreatePipedriveDealCommand]
):
    """Cria Deal garantindo Org e Person existentes."""

    def __init__(self, sync_service: PipedriveSyncService) -> None:
        self._sync = sync_service

    # ──────────────────────────────────────────────────────────
    async def handle(
        self, cmd: CreatePipedriveDealCommand
    ) -> dict[str, int | None]:
        # ---------- carrega o case ----------
        case_qs = (
            CollectionCase.objects
            .select_related(
                "patient__address",
                "clinic__data__address",
                "contract__payment_method",
            )
            .prefetch_related(
                Prefetch(
                    "clinic__phones",
                    queryset=ClinicPhone.objects.all(),
                    to_attr="prefetched_phones",
                ),
                Prefetch(
                    "contract__installments",
                    queryset=Installment.objects.all(),
                    to_attr="prefetched_installments",
                ),
                Prefetch(
                    "patient__phones",
                    queryset=PatientPhone.objects.all(),
                    to_attr="prefetched_phones",
                ),
            )
        )
        case: CollectionCase = await sync_to_async(case_qs.get)(
            id=cmd.collection_case_id
        )

        if case.deal_id:
            log.info("deal_already_exists", case_id=case.id)
            return {"deal_id": case.deal_id}

        # ---------- garante Org + Person ----------
        org_id = await self._sync.ensure_org_id(cnpj=case.clinic.cnpj)
        person_id = await sync_to_async(self._sync.ensure_person)(
            patient=case.patient, org_id=org_id
        )

        # ---------- monta payload ----------
        payload = await sync_to_async(
            lambda: PipedriveDealPayloadBuilder(case).build()
        )()
        payload.update({"org_id": org_id, "person_id": person_id})

        # ---------- chama API ----------
        response = await sync_to_async(self._sync.client.create_deal)(payload)

        deal_id = (
            response.get("json", {}).get("data", {}).get("id")
            if response.get("ok")
            else None
        )

        # ---------- persiste ----------
        if deal_id:
            case.deal_id = deal_id
            case.deal_sync_status = CollectionCase.DealSyncStatus.CREATED
            fields = ["deal_id", "deal_sync_status"]
            log.info("deal_created", case_id=case.id, deal_id=deal_id)
        else:
            case.deal_sync_status = CollectionCase.DealSyncStatus.ERROR
            fields = ["deal_sync_status"]
            log.error(
                "deal_creation_failed",
                case_id=case.id,
                status=response.get("status_code"),
                body=response.get("json") or response.get("text"),
            )

        await sync_to_async(case.save)(update_fields=fields)
        return {"deal_id": deal_id}
