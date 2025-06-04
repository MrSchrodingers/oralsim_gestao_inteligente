import structlog
from django.apps import AppConfig

logger = structlog.get_logger(__name__)

class DjangoInterfaceConfig(AppConfig):
    name = "plugins.django_interface"
    verbose_name = "Django Interface"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Aqui você pode importar signals, registrar hooks, etc.
        # Por exemplo, se tiver signals.py:
        #   import infrastructure.django_app.signals  # noqa
        logger.info("DjangoAppConfig ready")
