from __future__ import annotations

import logging
import os
import signal
from typing import Final

import django

# --- Bootstrap Django ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import contextlib  # noqa: E402

from amqp import Message  # noqa: E402
from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402
from kombu import Connection, Queue  # noqa: E402

from oralsin_core.adapters.message_broker.rabbitmq import sync_dlx, sync_exchange  # noqa: E402

# --- Configurações ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

ROUTES: Final[dict[str, str]] = {
    "old_debts": "sync_old_debts",
    "acordo_activities": "sync_acordo_activities",
    "seed_scheduling": "seed_scheduling",
}

# --- Definição das Filas ---
all_sync_queues: Final[list[Queue]] = [
    Queue(
        name=f"sync.{routing_key}",
        exchange=sync_exchange,
        routing_key=routing_key,
        queue_arguments={'x-dead-letter-exchange': sync_dlx.name}
    )
    for routing_key in ROUTES
]

# --- Callback do Consumidor ---
def on_sync_message(body: dict, message: Message) -> None:
    routing_key = message.delivery_info.get("routing_key")
    django_cmd = ROUTES.get(routing_key)

    LOGGER.info(
        "Mensagem de sync recebida: routing_key=%s, body=%s",
        routing_key,
        body
    )
    try:
        if not django_cmd:
            raise ValueError(f"Nenhum comando Django encontrado para a routing_key: {routing_key}")
        clinic_id = body.get("oralsin_clinic_id") or body.get("clinic_id")
        if not clinic_id:
            raise ValueError("Payload não contém 'oralsin_clinic_id'")

        call_command(django_cmd, clinic_id=clinic_id)
        message.ack()
        LOGGER.info("Comando '%s' executado para a clínica %s.", django_cmd, clinic_id)
    except Exception:
        LOGGER.exception("Falha ao processar mensagem de sync. Rejeitando.")
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
        queue_names = ", ".join(q.name for q in all_sync_queues)
        LOGGER.info("Conectado ao RabbitMQ. Aguardando mensagens em: %s", queue_names)
        with conn.Consumer(queues=all_sync_queues, callbacks=[on_sync_message]):
            while not stop_consuming:
                with contextlib.suppress(TimeoutError):
                    conn.drain_events(timeout=1)
    
    LOGGER.info("Consumidor finalizado com sucesso.")

if __name__ == "__main__":
    main()