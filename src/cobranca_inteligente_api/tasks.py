from __future__ import annotations

import time
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date, timedelta

import structlog
from celery import Task, chain, shared_task
from django.core.cache import cache
from django.core.management import call_command
from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO

from plugins.django_interface.models import Clinic, CollectionCase

log = structlog.get_logger(__name__)
api = OralsinAPIClient()

# ──────────────────────────────────────────────────────────────────────────
# Constantes de filas e parâmetros
# ──────────────────────────────────────────────────────────────────────────
QUEUE_SYNC          = "sync_process"
QUEUE_NOTIF_SERIAL  = "notifications_serial"  # fila “lenta” p/ notificação/carta
BUSY_RETRY_SECONDS  = 60                      # espera se o lock da clínica já estiver ocupado
CLINIC_LOCK_TTL_SEC = 30 * 60                 # 30min — ajuste conforme duração típica
TASK_RATE_LIMIT     = "60/m"                  # limite p/ provedores (ajuste se necessário)

# ──────────────────────────────────────────────────────────────────────────
# Base Task com DLQ
# ──────────────────────────────────────────────────────────────────────────
class BaseTaskWithDLQ(Task):
    """
    Envia p/ Dead Letter Queue quando falhar após todas as retentativas.
    Evita enviar na configuração 'task_always_eager'.
    """
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        is_eager = bool(getattr(self.app.conf, "task_always_eager", False))
        if is_eager:
            # Em eager, não há broker; apenas logamos o “redirecionamento”
            log.critical(
                "task.failed_eager_mode",
                task=self.name, task_id=task_id, error=str(exc),
                note="DLQ não utilizada em eager; apenas log."
            )
        else:
            log.critical(
                "task.failed_dlq_redirect",
                task=self.name, task_id=task_id, error=str(exc),
                queue="dead_letter"
            )
            # Reenfileira a MESMA task na DLQ com os mesmos args/kwargs
            self.app.send_task(
                self.name,
                args=args,
                kwargs=kwargs,
                queue="dead_letter",
                routing_key="dead_letter",
            )
        super().on_failure(exc, task_id, args, kwargs, einfo)

# ──────────────────────────────────────────────────────────────────────────
# Lock distribuído por clínica (evita concorrência do MESMO clinic_id)
# ──────────────────────────────────────────────────────────────────────────
@contextmanager
def clinic_lock(clinic_id: str, namespace: str, ttl: int = CLINIC_LOCK_TTL_SEC):
    """
    Usa o backend de cache (Redis recomendado) para garantir exclusão por clínica.
    """
    key = f"locks:{namespace}:clinic:{clinic_id}"
    acquired = cache.add(key, str(time.time()), ttl)  # True se adicionou a chave (lock obtido)
    try:
        yield acquired
    finally:
        if acquired:
            cache.delete(key)

# ──────────────────────────────────────────────────────────────────────────
# Funções utilitárias
# ──────────────────────────────────────────────────────────────────────────
def iter_clinic_dicts() -> Iterable[dict]:
    return Clinic.objects.values("id", "oralsin_clinic_id")

def iter_active_oralsin_ids() -> Iterable[str]:
    return Clinic.objects.values_list("oralsin_clinic_id", flat=True)

# ──────────────────────────────────────────────────────────────────────────
# Tarefas de Resync (por clínica)
# ──────────────────────────────────────────────────────────────────────────
@shared_task(
    base=BaseTaskWithDLQ, bind=True, max_retries=3, default_retry_delay=300,
    acks_late=True, queue=QUEUE_SYNC
)
def execute_resync_for_clinic(self, clinic_oralsin_id: str):
    """
    [Granular] Resync de inadimplência para UMA clínica.
    """
    try:
        today = date.today()
        initial_date = today - timedelta(days=15)
        final_date = today + timedelta(days=200)
        log.info(
            "resync.start",
            clinic_oralsin_id=clinic_oralsin_id,
            initial_date=initial_date.isoformat(),
            final_date=final_date.isoformat(),
        )
        call_command(
            "sync_inadimplencia",
            "--oralsin-clinic-id", clinic_oralsin_id,
            "--data-inicio", initial_date.isoformat(),
            "--data-fim", final_date.isoformat(),
        )
        log.info("resync.ok", clinic_oralsin_id=clinic_oralsin_id)
    except Exception as exc:
        log.error("resync.error", clinic_oralsin_id=clinic_oralsin_id, error=str(exc))
        raise self.retry(exc=exc)  # noqa: B904

@shared_task(queue=QUEUE_SYNC)
def schedule_daily_resync():
    """
    [Orquestração] Dispara uma tarefa de resync para cada clínica ativa.
    """
    clinic_ids = list(iter_active_oralsin_ids())
    for cid in clinic_ids:
        execute_resync_for_clinic.delay(cid)
    log.info("resync.enqueued", total=len(clinic_ids))

# ──────────────────────────────────────────────────────────────────────────
# Tarefas de Sync genéricas (por clínica)
# ──────────────────────────────────────────────────────────────────────────
@shared_task(
    base=BaseTaskWithDLQ, bind=True, max_retries=3, default_retry_delay=60,
    acks_late=True, queue=QUEUE_SYNC
)
def execute_sync_for_clinic(self, command_name: str, clinic_id: str):
    """
    [Genérica] Executa um comando que aceita --clinic-id.
    """
    try:
        log.info("sync.run", command=command_name, clinic_id=clinic_id)
        call_command(command_name, "--clinic-id", clinic_id)
        log.info("sync.ok", command=command_name, clinic_id=clinic_id)
    except Exception as exc:
        log.error("sync.error", command=command_name, clinic_id=clinic_id, error=str(exc))
        raise self.retry(exc=exc)  # noqa: B904

@shared_task(queue=QUEUE_SYNC)
def schedule_daily_syncs():
    """
    [Orquestração] Enfileira comandos de sync por clínica.
    """
    commands_to_run = ["sync_acordo_activities", "sync_old_debts"]
    clinic_ids: list[str] = list(Clinic.objects.values_list("oralsin_clinic_id", flat=True))
    for clinic_id in clinic_ids:
        for cmd in commands_to_run:
            execute_sync_for_clinic.delay(cmd, str(clinic_id))
    log.info("syncs.enqueued", clinics=len(clinic_ids), commands=len(commands_to_run))

# ──────────────────────────────────────────────────────────────────────────
# Tarefas do Pipedrive (deals)
# ──────────────────────────────────────────────────────────────────────────
@shared_task(
    base=BaseTaskWithDLQ, bind=True, max_retries=3, default_retry_delay=60,
    acks_late=True, queue=QUEUE_SYNC
)
def execute_pipedrive_command_for_case(self, command_name: str, collection_case_id: str):
    try:
        log.info("pd.run", command=command_name, case_id=collection_case_id)
        call_command(command_name, "--collection-case-id", collection_case_id)
        log.info("pd.ok", command=command_name, case_id=collection_case_id)
    except Exception as exc:
        log.error("pd.error", command=command_name, case_id=collection_case_id, error=str(exc))
        raise self.retry(exc=exc)  # noqa: B904

@shared_task(queue=QUEUE_SYNC)
def schedule_pipedrive_updates():
    log.info("pd.schedule.start")
    case_ids: list[str] = list(CollectionCase.objects.values_list("id", flat=True))
    for cid in case_ids:
        execute_pipedrive_command_for_case.delay("create_pipedrive_deal", str(cid))
        execute_pipedrive_command_for_case.delay("update_pipedrive_deal", str(cid))
    log.info("pd.schedule.enqueued", total=len(case_ids))

# ──────────────────────────────────────────────────────────────────────────
# Notificações & Cartas — Sequência por clínica + rate limit + lock
# ──────────────────────────────────────────────────────────────────────────
@shared_task(
    base=BaseTaskWithDLQ, bind=True, max_retries=2, default_retry_delay=180,
    acks_late=True, queue=QUEUE_NOTIF_SERIAL, rate_limit=TASK_RATE_LIMIT
)
def execute_command_for_clinic(self, command_name: str, clinic_id: str, id_field: str = "--clinic-id"):
    """
    Executa um comando para UMA clínica, com:
      - lock distribuído por clínica (evita concorrência do MESMO clinic_id)
      - rate_limit (evita estouro em providers)
    """
    lock_ns = f"cmd:{command_name}"
    with clinic_lock(clinic_id, lock_ns) as ok:
        if not ok:
            log.warning("clinic_lock.busy", command=command_name, clinic_id=clinic_id)
            raise self.retry(countdown=BUSY_RETRY_SECONDS)

        try:
            log.info("clinic.cmd.run", command=command_name, clinic_id=clinic_id, field=id_field)
            call_command(command_name, id_field, clinic_id)
            log.info("clinic.cmd.ok", command=command_name, clinic_id=clinic_id)
        except Exception as exc:
            log.error("clinic.cmd.error", command=command_name, clinic_id=clinic_id, error=str(exc))
            raise self.retry(exc=exc)  # noqa: B904

@shared_task(queue=QUEUE_NOTIF_SERIAL)
def schedule_daily_notifications():
    """
    [Orquestração] Sequencial por clínica:
      1) run_automated_notifications (usa oralsin_clinic_id)
      2) send_pending_letters        (usa PK interna 'id')
    Encadeado via chain → ordem garantida POR clínica.
    """
    clinics = list(iter_clinic_dicts())
    total = 0
    for c in clinics:
        # cadeia por clínica garante ordem (notif -> cartas)
        chain(
            execute_command_for_clinic.si("run_automated_notifications", str(c["oralsin_clinic_id"]), "--clinic-id"),
            execute_command_for_clinic.si("send_pending_letters",       str(c["id"]),               "--clinic-id"),
        ).apply_async(queue=QUEUE_NOTIF_SERIAL)
        total += 1

    log.info("notifications.schedule.enqueued", clinics=total)

# ──────────────────────────────────────────────────────────────────────────
# Atividades → Oralsin
# ──────────────────────────────────────────────────────────────────────────
@shared_task(name="notification_billing.process_activity")
def process_activity_task(payload: dict):
    """
    Processa uma atividade e envia à API da Oralsin.
    """
    try:
        dto = OralsinContatoHistoricoEnvioDTO(**payload)
        api.post_contact_history(dto)
        log.info("activity.sent_to_oralsin_via_celery", paciente_id=dto.idPaciente, contrato_id=dto.idContrato)
    except Exception as e:
        log.error("celery_task.process_activity.failed", error=str(e), payload=payload)
        raise
