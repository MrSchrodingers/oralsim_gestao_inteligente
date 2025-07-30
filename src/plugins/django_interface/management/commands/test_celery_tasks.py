from django.core.management.base import BaseCommand, CommandError

from cobranca_inteligente_api import tasks


class Command(BaseCommand):
    """
    Dispara uma tarefa Celery para fins de teste e depuração.
    Permite chamar tanto tarefas de orquestração quanto de execução individual.
    
    Exemplos de uso:
    - python manage.py test_celery_tasks schedule_daily_resync
    - python manage.py test_celery_tasks run_maintenance_command --task-args "ensure_schedules"
    - python manage.py test_celery_tasks execute_resync_for_clinic --task-args "<clinic_uuid>"
    - python manage.py test_celery_tasks execute_sync_for_clinic --task-args "sync_old_debts,<clinic_id>"
    """
    help = 'Dispara uma tarefa Celery para teste, com argumentos separados por vírgula.'

    # Mapeamento central de tarefas disponíveis para chamada.
    # Isso evita a execução de qualquer função arbitrária e serve como documentação.
    TASKS_MAP = {
        # Tarefas Orquestradoras
        'schedule_daily_resync': tasks.schedule_daily_resync,
        'schedule_daily_syncs': tasks.schedule_daily_syncs,
        'schedule_pipedrive_updates': tasks.schedule_pipedrive_updates,
        'schedule_daily_notifications': tasks.schedule_daily_notifications,

        # Tarefas de Execução (para testes granulares)
        'run_maintenance_command': tasks.run_maintenance_command,
        'execute_resync_for_clinic': tasks.execute_resync_for_clinic,
        'execute_sync_for_clinic': tasks.execute_sync_for_clinic,
        'execute_pipedrive_command_for_case': tasks.execute_pipedrive_command_for_case,
        'execute_command_for_clinic': tasks.execute_command_for_clinic,
    }

    def add_arguments(self, parser):
        """Define os argumentos que o comando aceita."""
        parser.add_argument(
            'task_name',
            type=str,
            choices=self.TASKS_MAP.keys(),  # Restringe as escolhas às tarefas mapeadas
            help='O nome da tarefa a ser testada.'
        )
        parser.add_argument(
            # CORREÇÃO: Renomeado de --args para --task-args para evitar conflito com o Django.
            '--task-args',
            type=str,
            help='Argumentos para a tarefa, separados por vírgula (ex: "arg1,arg2,arg3").'
        )

    def handle(self, *args, **options):
        """Lógica principal do comando."""
        task_name = options['task_name']
        task_args_str = options['task_args']

        # O 'choices' no add_argument já valida se a tarefa existe, 
        # mas mantemos uma verificação extra por segurança.
        task_to_run = self.TASKS_MAP.get(task_name)
        if not task_to_run:
            raise CommandError(f"Erro inesperado: Tarefa '{task_name}' não encontrada no mapa interno.")
        
        task_args = []
        if task_args_str:
            # Separa os argumentos pela vírgula e remove espaços em branco
            task_args = [arg.strip() for arg in task_args_str.split(',')]

        self.stdout.write(self.style.NOTICE(f"▶️  Enfileirando tarefa '{task_name}' com argumentos: {task_args}..."))
        
        try:
            # Dispara a tarefa com os argumentos desempacotados
            task_to_run.delay(*task_args)
            
            self.stdout.write(self.style.SUCCESS(f"✅ Tarefa '{task_name}' enfileirada com sucesso!"))
            self.stdout.write(self.style.WARNING("   Lembre-se de verificar o console do seu worker Celery e o dashboard do Flower para acompanhar a execução."))
        except Exception as e:
            raise CommandError(f"❌ Falha ao enfileirar a tarefa '{task_name}': {e}")  # noqa: B904
