# src/cobranca_inteligente_api/tasks.py

import logging
from datetime import date, timedelta

from celery import Task, shared_task
from django.core.management import call_command
from django.db.models import QuerySet

# Ajuste o caminho de importação conforme a localização real dos seus modelos
from plugins.django_interface.models import Clinic, CollectionCase

logger = logging.getLogger(__name__)


class BaseTaskWithDLQ(Task):
    """
    Classe base para tarefas Celery que implementa o roteamento para a Dead Letter Queue (DLQ)
    em caso de falha após todas as retentativas.
    """
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.critical(
            f"Task {self.name} [{task_id}] failed after retries. Sending to DLQ.",
            extra={"args": args, "kwargs": kwargs, "error": str(exc)}
        )
        self.app.send_task(
            self.name,
            args=args,
            kwargs=kwargs,
            queue='dead_letter',
            routing_key='dead_letter'
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)


# -----------------------------------------------------------------------------
# TAREFAS DE SINCRONIZAÇÃO DE DADOS (SYNC)
# -----------------------------------------------------------------------------

@shared_task(base=BaseTaskWithDLQ, bind=True, max_retries=3, default_retry_delay=300, acks_late=True)
def execute_resync_for_clinic(self, clinic_oralsin_id: str):
    """
    [Execução Granular] Executa a sincronização de inadimplência para UMA ÚNICA clínica.
    """
    try:
        today = date.today()
        initial_date = today - timedelta(days=1)
        final_date = today + timedelta(days=1)
        
        logger.info(f"Executando resync para clínica {clinic_oralsin_id} na janela de {initial_date} a {final_date}.")
        
        # CORREÇÃO: Chamamos um comando granular, não o 'resync_daily' que faz o loop.
        # Assumindo que a lógica do SyncInadimplenciaCommand está em um comando chamado 'sync_inadimplencia'.
        # Se o comando tiver outro nome, ajuste aqui.
        call_command(
            'sync_inadimplencia',  # Comando hipotético que encapsula SyncInadimplenciaCommand
            '--oralsin-clinic-id', clinic_oralsin_id,
            '--data-inicio', initial_date.isoformat(),
            '--data-fim', final_date.isoformat(),
            '--resync'
        )
    except Exception as exc:
        logger.error(f"Erro no resync da clínica {clinic_oralsin_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)  # noqa: B904

@shared_task
def schedule_daily_resync():
    """
    [Orquestração] Busca todas as clínicas ativas e dispara uma tarefa de resync para cada uma.
    """
    logger.info("Iniciando agendamento do resync diário para todas as clínicas.")
    active_clinics_ids: QuerySet[str] = Clinic.objects.filter(coverage__active=True).values_list("oralsin_clinic_id", flat=True)
    
    for clinic_id in active_clinics_ids:
        execute_resync_for_clinic.delay(clinic_id)
    
    logger.info(f"{len(list(active_clinics_ids))} tarefas de resync diário foram enfileiradas.")


@shared_task(base=BaseTaskWithDLQ, bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def execute_sync_for_clinic(self, command_name: str, clinic_id: str):
    """
    [Execução Genérica] Executa um comando que requer --clinic-id para uma clínica.
    """
    try:
        logger.info(f"Executando comando '{command_name}' para clinic_id: {clinic_id}")
        call_command(command_name, '--clinic-id', clinic_id)
    except Exception as exc:
        logger.error(f"Erro ao executar '{command_name}' para clinic_id {clinic_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)  # noqa: B904

@shared_task
def schedule_daily_syncs():
    """
    [Orquestração] Agenda a execução de múltiplos comandos de sincronização que iteram por clínica.
    """
    commands_to_run = ['sync_acordo_activities', 'sync_old_debts']
    logger.info(f"Agendando os seguintes comandos de sync para todas as clínicas: {commands_to_run}")
    
    clinic_ids: QuerySet[str] = Clinic.objects.filter(is_active=True).values_list('id', flat=True)
    
    for clinic_id in clinic_ids:
        for command in commands_to_run:
            execute_sync_for_clinic.delay(command, str(clinic_id))
    
    logger.info(f"Tarefas de sync enfileiradas para {len(list(clinic_ids))} clínicas.")


# -----------------------------------------------------------------------------
# TAREFAS DO PIPEDRIVE (DEALS)
# -----------------------------------------------------------------------------

@shared_task(base=BaseTaskWithDLQ, bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def execute_pipedrive_command_for_case(self, command_name: str, collection_case_id: str):
    """
    [Execução Genérica] Executa um comando Pipedrive para um CollectionCase.
    """
    try:
        logger.info(f"Executando '{command_name}' para collection_case_id: {collection_case_id}")
        call_command(command_name, '--collection-case-id', collection_case_id)
    except Exception as exc:
        logger.error(f"Erro ao executar '{command_name}' para collection_case_id {collection_case_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)  # noqa: B904

@shared_task
def schedule_pipedrive_updates():
    """
    [Orquestração] Busca todos os CollectionCase ativos e agenda tarefas de criação e atualização.
    """
    logger.info("Iniciando agendamento de criação/atualização de deals no Pipedrive.")
    case_ids: QuerySet[str] = CollectionCase.objects.filter(is_active=True).values_list('id', flat=True)
    
    for case_id in case_ids:
        execute_pipedrive_command_for_case.delay('create_pipedrive_deal', str(case_id))
        execute_pipedrive_command_for_case.delay('update_pipedrive_deal', str(case_id))
        
    logger.info(f"{len(list(case_ids))} pares de tarefas (create/update deal) foram enfileirados.")


# -----------------------------------------------------------------------------
# TAREFAS DE NOTIFICAÇÃO E CARTAS
# -----------------------------------------------------------------------------

@shared_task(base=BaseTaskWithDLQ, bind=True, max_retries=2, default_retry_delay=180, acks_late=True)
def execute_command_for_clinic(self, command_name: str, clinic_id: str, id_field: str = '--clinic-id'):
    """
    [Execução Genérica e Flexível] Executa um comando para uma clínica, permitindo especificar o nome do campo de ID.
    """
    try:
        logger.info(f"Executando '{command_name}' para clínica com ID {clinic_id} (usando campo {id_field}).")
        call_command(command_name, id_field, clinic_id)
    except Exception as exc:
        logger.error(f"Erro ao executar '{command_name}' para clínica {clinic_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)  # noqa: B904

@shared_task
def schedule_daily_notifications():
    """
    [Orquestração] Agenda a execução de notificações e envio de cartas para todas as clínicas.
    """
    logger.info("Agendando notificações e envio de cartas para todas as clínicas ativas.")
    active_clinics: QuerySet[dict] = Clinic.objects.filter(is_active=True).values('id', 'oralsin_clinic_id')

    for clinic in active_clinics:
        # Tarefa de notificação usa oralsin_clinic_id
        execute_command_for_clinic.delay(
            'run_automated_notifications', 
            str(clinic['oralsin_clinic_id']), 
            '--clinic-id' # O comando usa o UUID da clínica, não a PK interna
        )
        # Tarefa de cartas usa a PK interna (id)
        execute_command_for_clinic.delay(
            'send_pending_letters', 
            str(clinic['id']), 
            '--clinic-id'
        )

    logger.info(f"{len(list(active_clinics))} pares de tarefas (notificações/cartas) foram enfileirados.")


# -----------------------------------------------------------------------------
# TAREFAS DE MANUTENÇÃO
# -----------------------------------------------------------------------------

@shared_task(base=BaseTaskWithDLQ, bind=True, acks_late=True)
def run_maintenance_command(self, command_name: str):
    """
    [Execução] Executa um comando de manutenção, como o 'ensure_schedules'.
    """
    try:
        logger.info(f"Executando comando de manutenção: {command_name}")
        call_command(command_name)
    except Exception as exc:
        # Tarefas de manutenção geralmente não devem ter retentativas automáticas.
        # Se falhar, é melhor investigar manualmente.
        logger.critical(f"Erro CRÍTICO ao executar o comando de manutenção '{command_name}': {exc}", exc_info=True)
        raise  # A falha será capturada pela BaseTaskWithDLQ e enviada para a DLQ.