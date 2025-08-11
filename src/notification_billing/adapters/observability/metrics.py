from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)
from starlette.responses import Response

registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)

NOTIFICATION_FLOW_COUNT = Counter(
    "notification_flow_total",
    "Execucoes de fluxos de notificacao",
    ["mode", "success"],
    registry=registry,
)

NOTIFICATION_FLOW_DURATION = Histogram(
    "notification_flow_duration_seconds",
    "Duracao do fluxo de notificacao",
    ["mode"],
    registry=registry,
)


def metrics(request):
    data = generate_latest(registry)
    return Response(data, media_type=CONTENT_TYPE_LATEST)