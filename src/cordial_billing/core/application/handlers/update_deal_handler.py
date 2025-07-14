from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any

from asgiref.sync import sync_to_async
from django.db.models import Prefetch
from structlog import get_logger

from cordial_billing.core.application.commands.update_deal_command import (
    UpdatePipedriveDealCommand,
)
from cordial_billing.core.application.services.pipedrive_deal_payload_builder import (
    PipedriveDealPayloadBuilder,
)
from cordial_billing.core.application.services.pipedrive_sync_service import (
    PipedriveSyncService,
)
from cordial_billing.core.domain.repositories.activity_repository import ActivityRepository
from notification_billing.core.application.cqrs import CommandHandler
from plugins.django_interface.models import (
    ClinicPhone,
    CollectionCase,
    Installment,
    PatientPhone,
)

log = get_logger(__name__)

# Stage “ADM Verificar” no pipeline 3.
ADM_VERIFICAR_STAGE_ID = 22        # ajuste conforme seu Pipedrive


class UpdatePipedriveDealHandler(
    CommandHandler[UpdatePipedriveDealCommand]
):
    """
    • Sincroniza o valor ou a etapa de um Deal existente.
    • Cria uma Activity explicando o motivo da atualização.
    """

    def __init__(
        self,
        sync_service: PipedriveSyncService,
        activity_repo: ActivityRepository,
    ) -> None:
        self._sync  = sync_service
        self._acts  = activity_repo

    # -----------------------------------------------------------------
    async def handle(
        self, cmd: UpdatePipedriveDealCommand
    ) -> dict[str, Any]:
        # ----------- carrega CollectionCase + relacionamentos -------
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

        if not case.deal_id:
            log.warning("case_without_deal", case_id=case.id)
            return {"updated": False, "reason": "without_deal"}

        builder   = PipedriveDealPayloadBuilder(case)
        payload   = builder.build()              # reaproveita cálculo de valores
        new_value = payload["value"]             # float
        overdue   = builder._overdue_count()
        do_bill   = bool(case.contract.do_billings)

        # ------------------ 1) atualização de VALOR -----------------
        updates: dict[str, Any] = {}
        reason = None

        if Decimal(str(new_value)) != case.amount:
            updates["value"]    = new_value
            updates["currency"] = "BRL"
            reason = (
                f"Valor atualizado para R$ {new_value:,.2f}. "
                "Motivo: nova parcela vencida/pagamento registrado."
            )

        # ------------------ 2) mudança de ETAPA ---------------------
        if (overdue == 0 or not do_bill) and case.stage_id != ADM_VERIFICAR_STAGE_ID:
            updates["stage_id"] = ADM_VERIFICAR_STAGE_ID
            if reason:
                reason += " | "
            reason = (
                (reason or "")
                + (
                    "Paciente sem parcelas vencidas "
                    if overdue == 0 else
                    "Cobrança amigável desativada "
                )
                + "→ movido(a) para etapa ADM Verificar."
            )

        if not updates:
            log.info("deal_update_skip", deal_id=case.deal_id)
            return {"updated": False, "reason": "no_changes"}

        # ------------------ 3) chama API Pipedrive ------------------
        resp = await sync_to_async(
            self._sync.client._safe_request
        )(
            "patch",
            f"deals/{case.deal_id}",
            json_body=updates,
        )

        # ------------------ 4) cria Activity ------------------------
        if resp.get("ok"):
            await self._create_activity(
                deal_id=case.deal_id,
                subject="Atualização automática do negócio",
                note=reason,
            )
            log.info("deal_updated", deal_id=case.deal_id, updates=updates)
            # persiste últimos dados relevantes no Case
            if "stage_id" in updates:
                case.stage_id = updates["stage_id"]
            case.amount = Decimal(str(new_value))
            await sync_to_async(case.save)(update_fields=["stage_id", "amount"])
            return {"updated": True, "updates": updates}
        else:
            log.error(
                "deal_update_failed",
                deal_id=case.deal_id,
                status=resp.get("status_code"),
                body=resp.get("json") or resp.get("text"),
            )
            return {"updated": False, "reason": "api_error"}

    # -----------------------------------------------------------------
    async def _create_activity(self, *, deal_id: int, subject: str, note: str) -> None:
        """
        • Cria Activity no Pipedrive
        • Persiste no ActivityRepository
        """
        body = {
            "subject": subject,
            "note": note,
            "deal_id": deal_id,
            "done": 1,
            "due_date": _dt.date.today().isoformat(),
        }
        resp = await sync_to_async(self._sync.client._safe_request)(
            "post", "activities", json_body=body
        )
        if resp.get("ok"):
            act_id = resp["json"]["data"]["id"]
            await self._acts.save_from_pipedrive_json(resp["json"]["data"])
            log.info("activity_created", activity_id=act_id, deal_id=deal_id)
        else:
            log.error(
                "activity_create_failed",
                deal_id=deal_id,
                status=resp.get("status_code"),
                body=resp.get("json") or resp.get("text"),
            )
