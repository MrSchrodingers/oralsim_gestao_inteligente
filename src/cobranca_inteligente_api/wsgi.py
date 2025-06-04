import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

# 1) Ajuste padrão de settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# 2) Inicializa DI do Core
from oralsin_core.adapters.config.composition_root import setup_di_container_from_settings as setup_core_di

setup_core_di(settings)

# 3) Inicializa DI do Notification Billing
from notification_billing.adapters.config.composition_root import setup_di_container_from_settings as setup_nb_di  # noqa: E402

setup_nb_di(settings)

# 4) Cria a aplicação WSGI
application = get_wsgi_application()
