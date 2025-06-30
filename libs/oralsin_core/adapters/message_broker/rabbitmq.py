from __future__ import annotations

import json
from datetime import date, datetime
from uuid import UUID

import structlog
from kombu import Connection, Exchange
from kombu.pools import producers
from kombu.serialization import register

log = structlog.get_logger()

# --- Definição Central de Exchanges ---
registration_exchange = Exchange("registration", type="direct")
registration_dlx = Exchange("registration.dlx", type="fanout")
sync_exchange = Exchange("sync", type="direct")
sync_dlx = Exchange("sync.dlx", type="fanout")

# --- Serializer Customizado ---
def _default_serializer(obj):
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def dumps(data):
    return json.dumps(data, default=_default_serializer)

register('custom_json', dumps, json.loads, content_type='application/json', content_encoding='utf-8')

# --- CLASSE DE SERVIÇO DE MENSAGENS (A ÚNICA INTERFACE) ---
class MessagingService:
    def __init__(self, rabbitmq_url: str):
        if not rabbitmq_url:
            raise ValueError("A URL do RabbitMQ é obrigatória.")
        self.rabbitmq_url = rabbitmq_url
        log.info("MessagingService initialized")

    def publish(self, exchange: Exchange, routing_key: str, message: dict):
        log.info("Publishing message", exchange=exchange.name, routing_key=routing_key)
        try:
            with Connection(self.rabbitmq_url) as conn, producers[conn].acquire(block=True) as producer:
                producer.publish(
                    body=message,
                    exchange=exchange,
                    routing_key=routing_key,
                    serializer='custom_json',
                    compression='gzip',
                    retry=True,
                    retry_policy={
                        'interval_start': 0, 'interval_step': 2,
                        'interval_max': 30, 'max_retries': 3,
                    }
                )
            log.info("Message published successfully", exchange=exchange.name)
        except Exception:
            log.exception("Failed to publish message")
            raise

# A API pública deste módulo é a classe e as exchanges. Nada mais.
__all__ = [
    "MessagingService",
    "registration_exchange",
    "registration_dlx",
    "sync_exchange",
    "sync_dlx",
]