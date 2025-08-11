from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route

# — Cria um registry exclusivo e injeta o collector multiprocess
registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)

# — HTTP (views REST)
HTTP_REQUEST_LATENCY = Histogram(
    'billing_request_duration_seconds',
    'Latência de requisições HTTP',
    ['method', 'view', 'status'],
    registry=registry,
)
HTTP_REQUEST_COUNT = Counter(
    'billing_requests_total',
    'Total de requisições HTTP',
    ['method', 'view', 'status'],
    registry=registry,
)

# — Cache Redis
CACHE_HITS = Counter(
    'cache_hits_total', 'Hits no cache Redis', ['service'], registry=registry
)
CACHE_MISSES = Counter(
    'cache_misses_total', 'Misses no cache Redis', ['service'], registry=registry
)

# — Sync Service
SYNC_RUNS = Counter(
    'sync_runs_total',
    'Número de execuções do OralsinSyncService',
    ['clinic'],
    registry=registry,
)
SYNC_PATIENTS = Counter(
    'sync_patients_synced_total',
    'Pacientes sincronizados por execução',
    ['clinic'],
    registry=registry,
)
SYNC_DURATION = Histogram(
    'sync_duration_seconds',
    'Duração do sync Oralsin',
    ['clinic'],
    registry=registry,
)

# — Dashboard Business
BUSINESS_TOTAL_RECEIVABLES = Gauge(
    'business_total_receivables', 'Valor total a receber', ['clinic'], registry=registry
)
BUSINESS_OVERDUE_PAYMENTS = Gauge(
    'business_overdue_payments', 'Valor de pagamentos atrasados', ['clinic'], registry=registry
)
BUSINESS_COLLECTION_RATE = Gauge(
    'business_collection_rate', 'Taxa de recuperação (%)', ['clinic'], registry=registry
)
# — Outros indicadores de negócio
BUSINESS_TOTAL_CONTRACTS = Gauge(
    'business_total_contracts', 'Total de contratos', ['clinic'], registry=registry
)
BUSINESS_TOTAL_PATIENTS = Gauge(
    'business_total_patients', 'Total de pacientes', ['clinic'], registry=registry
)
BUSINESS_AVG_OVERDUE_DAYS = Gauge(
    'business_avg_days_overdue', 'Média de dias em atraso', ['clinic'], registry=registry
)
# — Notifications
NOTIFICATIONS_SENT = Counter(
    'notifications_sent_total',
    'Notificações enviadas',
    ['mode', 'channel', 'success'],
    registry=registry,
)

# — RabbitMQ
RABBITMQ_PUBLISHED = Counter(
    'rabbitmq_messages_published',
    'Mensagens publicadas no RabbitMQ',
    ['exchange', 'routing_key'],
    registry=registry,
)
RABBITMQ_CONSUMED = Counter(
    'rabbitmq_messages_consumed',
    'Mensagens consumidas do RabbitMQ',
    ['queue'],
    registry=registry,
)

# — Expondo via ASGI com Starlette
async def metrics(request):
    data = generate_latest(registry)
    return Response(data, media_type=CONTENT_TYPE_LATEST)

app = Starlette(routes=[
    Route("/metrics", metrics),
])
