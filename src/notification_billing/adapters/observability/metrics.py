import os

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route

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

app = Starlette(routes=[Route("/metrics", metrics)])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "notification_billing.adapters.observability.metrics:app",
        host="0.0.0.0",
        port=int(os.getenv("APP_METRICS_PORT", 9109)),
    )