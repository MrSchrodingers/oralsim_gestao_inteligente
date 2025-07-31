from __future__ import annotations

import logging
import os
import signal
from concurrent.futures import ThreadPoolExecutor

import django
from django.core.management import call_command
from django.db import transaction

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import contextlib  # noqa: E402

from amqp import Message  # noqa: E402
from django.conf import settings  # noqa: E402
from kombu import Connection, Queue  # noqa: E402

from oralsin_core.adapters.message_broker.rabbitmq import (  # noqa: E402
    MessagingService,
    registration_dlx,
    registration_exchange,
    sync_exchange,
)

# --- Configurações ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

SYNC_ROUTING_KEYS = ("old_debts", "acordo_activities", "seed_scheduling")
EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="seed-worker")

# --- Definição da Fila ---
registration_approved_queue = Queue(
    name='registration.approved',
    exchange=registration_exchange,
    routing_key='approved',
    queue_arguments={'x-dead-letter-exchange': registration_dlx.name}
)

# --- Lógica de Negócio ---
def _publish_sync_tasks(clinic_id: int) -> None:
    messaging_service = MessagingService(rabbitmq_url=settings.RABBITMQ_URL)
    LOGGER.info("Publicando tarefas de sync para a clínica %s", clinic_id)
    for rk in SYNC_ROUTING_KEYS:
        messaging_service.publish(sync_exchange, rk, {"oralsin_clinic_id": clinic_id})

def _run_seed_and_sync(*, clinic_name: str, owner_name: str, min_days_billing: int, email: str, password: str) -> None:
    LOGGER.info("🛠 Seed para '%s' iniciado…", clinic_name)
    oralsin_clinic_id = None # Inicializa a variável
    try:
        with transaction.atomic():
            # O comando seed_data agora é a fonte da verdade para a criação
            call_command(
                "seed_data", clinic_name=clinic_name, owner_name=owner_name,
                min_days_billing=min_days_billing, skip_admin=True,
                skip_full_sync=False, clinic_email=email, clinic_pass=password,
                force=True, resync=False
            )
            # Após o comando rodar com sucesso, buscamos o ID para as próximas etapas
            from plugins.django_interface.models import CoveredClinic
            oralsin_clinic_id = CoveredClinic.objects.only("oralsin_clinic_id").get(name__iexact=clinic_name).oralsin_clinic_id
        
        LOGGER.info("✅ Seed concluído para %s (oralsin_clinic_id=%s)", clinic_name, oralsin_clinic_id)
        _publish_sync_tasks(oralsin_clinic_id)
        LOGGER.info("📤 Sync tasks publicadas para clínica id=%s", oralsin_clinic_id)

    except Exception:
        LOGGER.exception("Seed falhou para %s. Enviando para DLX.", clinic_name)
        messaging_service = MessagingService(rabbitmq_url=settings.RABBITMQ_URL)
        payload = {"clinic_name": clinic_name, "owner_name": owner_name, "error": "seed_failed"}
        messaging_service.publish(registration_dlx, "seed_failed", payload)

# --- Callback do Consumidor ---
def on_message_received(body: dict, message: Message) -> None:
    try:
        LOGGER.info("Mensagem de aprovação recebida: %s", body)
        clinic_name = body["clinic_name"]
        owner_name = body["name"]
        min_days_billing = body["cordial_billing_config"]
        email = body.get("email")
        password = body.get("password") or body.get("password_hash")

        EXECUTOR.submit(
            _run_seed_and_sync,
            clinic_name=clinic_name, owner_name=owner_name,
            min_days_billing=min_days_billing, email=email, password=password
        )
        message.ack()
        LOGGER.info("ACK enviado e tarefa de seed para '%s' agendada.", clinic_name)
    except Exception:
        LOGGER.exception("Payload inválido ou erro inesperado. Rejeitando mensagem.")
        message.reject(requeue=False)

# --- Função Principal ---
def main():
    stop_consuming = False
    def graceful_shutdown(signum, frame):
        nonlocal stop_consuming
        LOGGER.info("Shutdown solicitado...")
        stop_consuming = True

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    with Connection(settings.RABBITMQ_URL) as conn:
        with conn.channel() as channel:
            LOGGER.info("Declarando dead-letter exchange '%s'", registration_dlx.name)
            registration_dlx.declare(channel=channel)
            
        LOGGER.info("Conectado ao RabbitMQ. Aguardando mensagens em '%s'", registration_approved_queue.name)
        with conn.Consumer(queues=[registration_approved_queue], callbacks=[on_message_received]):
            while not stop_consuming:
                with contextlib.suppress(TimeoutError):
                    conn.drain_events(timeout=1)
    
    LOGGER.info("Loop de consumo finalizado. Aguardando tarefas em background...")
    EXECUTOR.shutdown(wait=True)
    LOGGER.info("Consumidor finalizado com sucesso.")

if __name__ == "__main__":
    main()