from __future__ import annotations

import json

import structlog
from django.conf import settings
from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO

from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ, retry_consume

log = structlog.get_logger(__name__)
api = OralsinAPIClient()

_EXCHANGE = "oralsin.activities"
_QUEUE = _EXCHANGE
_ROUTING_KEY = "call"

rabbit = RabbitMQ(url=settings.RABBITMQ_URL)
ch = rabbit.channel()
ch.basic_qos(prefetch_count=50)   # tuning
    
@retry_consume(queue=_QUEUE)
def _on_message(ch, method, _props, body):
    dto = OralsinContatoHistoricoEnvioDTO(**json.loads(body))
    api.post_contact_history(dto)
    log.info("activity.sent_to_oralsin", activity_id=dto.idContrato or "sem-contrato")

ch.basic_consume(_QUEUE, on_message_callback=_on_message)
log.info("[*] Waiting for acordo_fechado activities…")
ch.start_consuming()