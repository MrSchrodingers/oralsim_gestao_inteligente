import json

import structlog
from django.conf import settings
from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO

from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ, retry_consume

log = structlog.get_logger(__name__)
api = OralsinAPIClient()

# --- 1. Definimos o exchange, a fila e AMBAS as chaves de roteamento ---
EXCHANGE = "oralsin.activities"
QUEUE_NAME = "oralsin.activities.processor" 
ROUTING_KEY_ACORDO = "acordo_fechado"
ROUTING_KEY_CONTATO = "contato_realizado"

# --- 2. Configuramos o RabbitMQ ---
rabbit = RabbitMQ(url=settings.RABBITMQ_URL)

# Declara o exchange e a fila (garante que existam)
rabbit.declare_exchange(EXCHANGE)
rabbit.declare_queue(QUEUE_NAME)

# --- 3. Vinculamos (bind) a MESMA fila às DUAS chaves de roteamento ---
rabbit.bind_queue(QUEUE_NAME, EXCHANGE, ROUTING_KEY_ACORDO)
rabbit.bind_queue(QUEUE_NAME, EXCHANGE, ROUTING_KEY_CONTATO)

# --- 4. O consumidor ouve a fila, que agora recebe ambas as mensagens ---
ch = rabbit.channel()
ch.basic_qos(prefetch_count=50)

@retry_consume(queue=QUEUE_NAME)
def on_message(ch, method, _props, body):
    """
    Esta função agora processará mensagens de AMBOS os tipos,
    pois ambas são direcionadas para a mesma fila.
    """
    routing_key = method.routing_key
    log.info("activity.received", routing_key=routing_key)
    
    dto = OralsinContatoHistoricoEnvioDTO(**json.loads(body))
    api.post_contact_history(dto)
    
    log.info(
        "activity.sent_to_oralsin",
        routing_key=routing_key,
        paciente_id=dto.idPaciente,
        contrato_id=dto.idContrato
    )

ch.basic_consume(QUEUE_NAME, on_message_callback=on_message)
log.info(f"[*] Waiting for activities on queue '{QUEUE_NAME}'...")
ch.start_consuming()