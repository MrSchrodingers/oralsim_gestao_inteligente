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

SYNC_DURATION = Histogram(
    "cordial_sync_duration_seconds",
    "Tempo de execucao do SyncOldDebtsHandler",
    ["clinic"],
    registry=registry,
)

CASES_CREATED = Counter(
    "cordial_cases_created_total",
    "CollectionCases criados",
    ["clinic"],
    registry=registry,
)

CASES_SKIPPED = Counter(
    "cordial_cases_skipped_total",
    "Parcelas ignoradas na criacao de CollectionCase",
    ["clinic"],
    registry=registry,
)


def metrics(request):
    data = generate_latest(registry)
    return Response(data, media_type=CONTENT_TYPE_LATEST)

app = Starlette(routes=[Route("/metrics", metrics)])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "cordial_billing.adapters.observability.metrics:app",
        host="0.0.0.0",
        port=int(os.getenv("APP_METRICS_PORT", 9110)),
    )