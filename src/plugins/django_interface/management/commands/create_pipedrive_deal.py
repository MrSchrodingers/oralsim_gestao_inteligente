from django.core.management.base import BaseCommand

from cordial_billing.adapters.config.composition_root import (
    setup_di_container_from_settings as cordial_container,
)
from cordial_billing.core.application.commands.create_deal_command import (
    CreatePipedriveDealCommand,
)


class Command(BaseCommand):
    """
    Cria (ou reaproveita) um Deal no Pipedrive para o CollectionCase informado.

    Uso:
        python manage.py create_pipedrive_deal --collection-case-id <UUID>
    """

    help = "Cria/sincroniza Deal no Pipedrive para um CollectionCase"

    def add_arguments(self, parser):
        parser.add_argument(
            "--collection-case-id",
            "-c",
            required=True,
            type=str,
            help="UUID do CollectionCase",
        )

    # -----------------------------------------------------------------
    def handle(self, *args, **opts):
        container = cordial_container(None)          # DI container singleton
        bus       = container.command_bus()

        result = bus.dispatch(
            CreatePipedriveDealCommand(
                collection_case_id=opts["collection_case_id"],
            )
        )

        self.stdout.write(self.style.SUCCESS(f"Resultado: {result}"))
