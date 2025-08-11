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