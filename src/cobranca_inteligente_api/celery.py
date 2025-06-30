import os

from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('cobranca_inteligente_api')
app.config_from_object('django.conf:settings', namespace='CELERY', force=True)

tasks_to_discover = list(settings.INSTALLED_APPS) 
tasks_to_discover.append('oralsin_core.adapters.message_broker') 
app.autodiscover_tasks(tasks_to_discover)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')