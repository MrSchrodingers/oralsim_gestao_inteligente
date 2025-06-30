import logging

from celery import group, shared_task
from django.core.management import call_command

from oralsin_core.adapters.config.composition_root import (
    setup_di_container_from_settings as setup_core_container,
)
from oralsin_core.core.application.commands.user_commands import CreateUserCommand
from oralsin_core.core.application.dtos.user_dto import CreateUserDTO
from plugins.django_interface.models import Clinic as ClinicModel

logger = logging.getLogger(__name__)

# Adicionamos queue='sync_process' para direcionar a tarefa
@shared_task(bind=True, max_retries=3, queue='sync_process')
def seed_data_task(self, registration_data: dict):
    """
    Tarefa Celery para executar o comando seed_data, que é o mais demorado.
    Retorna os dados necessários para o próximo passo.
    """
    clinic_name = registration_data['clinic_name']
    logger.info(f"[TASK] Iniciando 'seed_data' para a clínica: {clinic_name}")
    try:
        call_command(
            'seed_data',
            clinic_name=clinic_name,
            owner_name=registration_data['name'],
            min_days_billing=registration_data['cordial_billing_config'],
            skip_admin=True,
            skip_clinic_user=True,
            skip_full_sync=True,
        )
        logger.info(f"[TASK] 'seed_data' para '{clinic_name}' concluído com sucesso.")
        clinic_model = ClinicModel.objects.get(name=clinic_name)
        return {
            "registration_data": registration_data,
            "clinic_id": str(clinic_model.id),
            "oralsin_clinic_id": clinic_model.oralsin_clinic_id,
        }
    except Exception as exc:
        logger.error(f"[TASK-ERROR] Falha em 'seed_data' para a clínica '{clinic_name}': {exc}")
        raise self.retry(exc=exc, countdown=60)  # noqa: B904

# Adicionamos queue='sync_process' aqui também
@shared_task(bind=True, max_retries=3, queue='sync_process')
def post_seed_setup_task(self, previous_task_result: dict):
    """
    Tarefa que executa após o seed_data.
    1. Cria o usuário da clínica.
    2. Dispara as sincronizações restantes em paralelo.
    """
    registration_data = previous_task_result['registration_data']
    clinic_id = previous_task_result['clinic_id']
    oralsin_clinic_id = previous_task_result['oralsin_clinic_id']
    clinic_name = registration_data['clinic_name']

    logger.info(f"[TASK] Iniciando setup pós-seed para a clínica: {clinic_name}")
    try:
        core_container = setup_core_container(None)
        command_bus = core_container.command_bus()
        user_dto = CreateUserDTO(
            email=registration_data['email'],
            password_hash=registration_data['password_hash'],
            name=registration_data['name'],
            role="clinic",
            clinic_id=clinic_id
        )
        command_bus.dispatch(CreateUserCommand(payload=user_dto))
        logger.info(f"[TASK] Usuário para a clínica '{clinic_name}' criado.")

        sync_tasks = group(
            run_sync_command_task.s('sync_old_debts', oralsin_clinic_id),
            run_sync_command_task.s('sync_acordo_activities', oralsin_clinic_id),
            run_sync_command_task.s('seed_scheduling', oralsin_clinic_id)
        )
        sync_tasks.apply_async()
        
        logger.info(f"[TASK] Sincronizações em paralelo para '{clinic_name}' agendadas.")
        return f"Setup completo para a clínica {clinic_name}."
    except Exception as exc:
        logger.error(f"[TASK-ERROR] Falha no setup pós-seed para '{clinic_name}': {exc}")
        raise self.retry(exc=exc, countdown=60)  # noqa: B904

# E aqui também, para que o 'group' envie para a fila correta
@shared_task(max_retries=3, default_retry_delay=60, queue='sync_process')
def run_sync_command_task(command_name: str, oralsin_clinic_id: int):
    """
    Tarefa genérica para executar um comando de sincronização.
    """
    logger.info(f"[TASK] Executando comando de sync '{command_name}' para oralsin_clinic_id: {oralsin_clinic_id}")
    try:
        call_command(command_name, clinic_id=oralsin_clinic_id)
        logger.info(f"[TASK] Comando '{command_name}' para oralsin_clinic_id {oralsin_clinic_id} concluído.")
    except Exception as e:
        logger.error(f"[TASK-ERROR] Erro ao executar '{command_name}' para {oralsin_clinic_id}: {e}")
        raise