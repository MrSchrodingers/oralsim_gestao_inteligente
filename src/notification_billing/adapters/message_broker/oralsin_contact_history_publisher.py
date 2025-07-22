from __future__ import annotations

import json

import structlog
from django.conf import settings

from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ
from notification_billing.core.application.services.oralsin_payload_builder import (
    build_oralsin_payload,
)
from notification_billing.core.domain.events.contact_history_events import (
    ContactHistoryCreated,
)
from plugins.django_interface.models import ContactHistory

log = structlog.get_logger(__name__)
_EXCHANGE, _ROUTING_KEY = "oralsin.activities", "call"
rabbit = RabbitMQ(url=settings.RABBITMQ_URL)

@ContactHistoryCreated.subscribe
def publish_to_queue(event: ContactHistoryCreated) -> None:
    history = ContactHistory.objects.get(id=event.entity_id)
    dto = build_oralsin_payload(history)
    rabbit.channel().basic_publish(
        exchange=_EXCHANGE,
        routing_key=_ROUTING_KEY,
        body=json.dumps(dto.model_dump(by_alias=True, exclude_none=True)),
        properties=rabbit.persistent_props,
    )
    log.info("contact_history.enqueued", history_id=history.id)
