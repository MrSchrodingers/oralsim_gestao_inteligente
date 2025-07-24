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

# Etapa para onde os deals são movidos quando a cobrança é pausada ou concluída.
# Ex: "ADM Verificar", "Auditoria", "Cobrança Pausada", etc.
INACTIVE_BILLING_STAGE_ID = 26


class UpdatePipedriveDealHandler(CommandHandler[UpdatePipedriveDealCommand]):
    """
    • Sincroniza o valor ou a etapa de um Deal existente no Pipedrive.
    • Implementa a lógica robusta para pausar e restaurar a etapa de cobrança
      com base na flag `do_billings` do contrato.
    • Cria uma Activity explicando o motivo da atualização.
    """

    def __init__(
        self,
        sync_service: PipedriveSyncService,
        activity_repo: ActivityRepository,
    ) -> None:
        self._sync = sync_service
        self._acts = activity_repo

    async def handle(self, cmd: UpdatePipedriveDealCommand) -> dict[str, Any]:
        case = await self._load_full_collection_case(cmd.collection_case_id)

        if not case or not case.deal_id:
            log.warning(
                "case_update_skipped",
                case_id=cmd.collection_case_id,
                reason="Case or deal_id not found",
            )
            return {"updated": False, "reason": "without_case_or_deal"}

        builder = PipedriveDealPayloadBuilder(case)
        updates: dict[str, Any] = {}
        reason_parts = []

        # --- 1. LÓGICA DE ATUALIZAÇÃO DE VALOR (Existente) ---
        new_value = builder.build()["value"]  # float
        if Decimal(str(new_value)) != case.amount:
            updates["value"] = new_value
            updates["currency"] = "BRL"
            reason_parts.append(
                f"Valor atualizado para R$ {new_value:,.2f} devido a novas parcelas ou pagamentos."
            )

        # --- 2. NOVA LÓGICA DE TRANSIÇÃO DE ETAPA (baseada em `do_billings`) ---
        is_billing_active = bool(case.contract.do_billings)
        is_currently_in_inactive_stage = case.stage_id == INACTIVE_BILLING_STAGE_ID
        overdue_count = builder._overdue_count()
        
        # Cenário A: O paciente não tem mais dívidas vencidas. Mover para a etapa de verificação.
        if overdue_count == 0 and not is_currently_in_inactive_stage:
            updates["stage_id"] = INACTIVE_BILLING_STAGE_ID
            reason_parts.append("Paciente sem parcelas vencidas, movido para verificação.")

        # Cenário B: Cobrança foi DESATIVADA (true -> false)
        elif not is_billing_active and not is_currently_in_inactive_stage:
            # Salva a etapa atual antes de mover para a inativa
            case.last_stage_id = case.stage_id
            updates["stage_id"] = INACTIVE_BILLING_STAGE_ID
            reason_parts.append(
                f"Cobrança desativada. Posição anterior (Etapa ID: {case.last_stage_id}) salva. Movido para verificação."
            )

        # Cenário C: Cobrança foi REATIVADA (false -> true)
        elif is_billing_active and is_currently_in_inactive_stage and case.last_stage_id:
            # Restaura a etapa a partir da "memória"
            updates["stage_id"] = case.last_stage_id
            reason_parts.append(
                f"Cobrança reativada. Retornando para a etapa anterior (Etapa ID: {updates['stage_id']})."
            )
            # Limpa a memória após o uso para garantir a idempotência
            case.last_stage_id = None
        
        # --- 3. VERIFICAÇÃO FINAL E EXECUÇÃO ---
        if not updates:
            log.info("deal_update_skip", deal_id=case.deal_id, reason="no_changes_needed")
            return {"updated": False, "reason": "no_changes"}

        final_reason = " | ".join(reason_parts)

        # --- 4. CHAMA API PIPEDRIVE E PERSISTE O ESTADO ---
        resp = await self._update_pipedrive_deal(case.deal_id, updates)

        if resp.get("ok"):
            await self._create_activity(deal_id=case.deal_id, subject="Atualização Automática do Negócio", note=final_reason)
            log.info("deal_updated", deal_id=case.deal_id, updates=updates)
            
            # Persiste as alterações no nosso banco de dados
            # A transação é garantida pelo case.save() que atualiza todos os campos de uma vez.
            if "stage_id" in updates:
                case.stage_id = updates["stage_id"]
            if "value" in updates:
                case.amount = Decimal(str(updates["value"]))
            
            # O save irá persistir stage_id, last_stage_id (que pode ter sido alterado) e amount
            await sync_to_async(case.save)(update_fields=["stage_id", "last_stage_id", "amount"])
            
            return {"updated": True, "updates": updates}
        else:
            log.error(
                "deal_update_failed",
                deal_id=case.deal_id,
                status=resp.get("status_code"),
                body=resp.get("json") or resp.get("text"),
            )
            return {"updated": False, "reason": "api_error"}

    async def _load_full_collection_case(self, case_id: str) -> CollectionCase | None:
        """Carrega o CollectionCase e todas as suas dependências com prefetch para otimização."""
        try:
            case_qs = (
                CollectionCase.objects.select_related(
                    "patient__address",
                    "clinic__data__address",
                    "contract__payment_method",
                )
                .prefetch_related(
                    Prefetch("clinic__phones", queryset=ClinicPhone.objects.all(), to_attr="prefetched_phones"),
                    Prefetch("contract__installments", queryset=Installment.objects.all(), to_attr="prefetched_installments"),
                    Prefetch("patient__phones", queryset=PatientPhone.objects.all(), to_attr="prefetched_phones"),
                )
            )
            return await sync_to_async(case_qs.get)(id=case_id)
        except CollectionCase.DoesNotExist:
            return None

    async def _update_pipedrive_deal(self, deal_id: int, payload: dict) -> dict:
        """Encapsula a chamada à API para atualizar o deal."""
        return await sync_to_async(self._sync.client._safe_request)(
            "patch", f"deals/{deal_id}", json_body=payload
        )

    async def _create_activity(self, *, deal_id: int, subject: str, note: str) -> None:
        """Cria uma Activity no Pipedrive e a persiste localmente."""
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