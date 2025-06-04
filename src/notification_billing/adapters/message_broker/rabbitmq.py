import json
from functools import wraps
from uuid import UUID

import pika
import structlog
from pika.adapters.blocking_connection import BlockingChannel

logger = structlog.get_logger()

def _serialize_message(msg: dict) -> dict:
    out = {}
    for k, v in msg.items():
        if isinstance(v, UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out

class RabbitMQ:
    def __init__(self, url: str):
        self._params = pika.URLParameters(url)
        self._conn = None

    def connect(self):
        if self._conn is None or self._conn.is_closed:
            self._conn = pika.BlockingConnection(self._params)
        return self._conn

    def channel(self) -> BlockingChannel:
        return self.connect().channel()

    def declare_queue(self, name: str, dlx: str = None):
        ch = self.channel()
        args = {}
        if dlx:
            args['x-dead-letter-exchange'] = dlx
        ch.queue_declare(queue=name, durable=True, arguments=args)

    def declare_exchange(self, name: str, exchange_type='direct', dlx: str = None):
        ch = self.channel()
        args = {}
        if dlx:
            args['x-dead-letter-exchange'] = dlx
        ch.exchange_declare(exchange=name, exchange_type=exchange_type, durable=True, arguments=args)

    def bind_queue(self, queue: str, exchange: str, routing_key: str):
        ch = self.channel()
        ch.queue_bind(queue=queue, exchange=exchange, routing_key=routing_key)

    def publish(self, exchange: str, routing_key: str, message: dict):
        ch = self.channel()
        serialized = _serialize_message(message)
        ch.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(serialized).encode(),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logger.info("rabbitmq.published", exchange=exchange, routing_key=routing_key, message=message)

# Decorator para publicar saída de uma função como mensagem
def publish(exchange: str, routing_key: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            from django.conf import settings

            from notification_billing.adapters.config.composition_root import setup_di_container_from_settings
            
            setup_di_container_from_settings(settings)
            
            from notification_billing.adapters.config.composition_root import container
            
            rabbit: RabbitMQ = container.rabbit()
            rabbit.publish(exchange, routing_key, result)
            return result
        return wrapper
    return decorator

# Decorator para consumo com retry/backoff
import backoff  # noqa: E402


def retry_consume(max_tries=5, base=1.0):
    def deco(fn):
        @backoff.on_exception(backoff.expo, pika.exceptions.AMQPError, max_tries=max_tries)
        @wraps(fn)
        def wrapper(ch, method, properties, body):
            data = json.loads(body)
            try:
                fn(ch, method, properties, data)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                logger.exception("rabbitmq.consume.failed", data=data)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return wrapper
    return deco
