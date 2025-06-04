import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('PROMETHEUS_MULTIPROC_DIR', '/tmp/prometheus')

import django
from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application

django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # websocket etc…
})
