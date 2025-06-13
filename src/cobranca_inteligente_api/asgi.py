import os

from config.structlog_config import configure_logging

configure_logging(level="DEBUG")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('PROMETHEUS_MULTIPROC_DIR', '/tmp/prometheus')

import django  # noqa: E402
from channels.routing import ProtocolTypeRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # websocket etc…
})
