import os

from celery import Celery

# Define o módulo de configurações do Django para o Celery.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Cria a instância do app Celery.
app = Celery('cobranca_inteligente_api')

# Carrega a configuração a partir do arquivo settings.py do Django.
# O namespace 'CELERY' significa que todas as configurações do Celery devem
# começar com CELERY_ (ex: CELERY_BROKER_URL).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Isso instrui o Celery a inspecionar todos os apps em settings.INSTALLED_APPS
# em busca de um arquivo chamado tasks.py, que é o padrão e a melhor prática.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Uma tarefa de debug para verificar se o worker está funcionando."""
    print(f'Request: {self.request!r}')