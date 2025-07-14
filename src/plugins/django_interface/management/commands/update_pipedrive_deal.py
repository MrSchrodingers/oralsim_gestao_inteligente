from django.core.management.base import BaseCommand

from cordial_billing.adapters.config.composition_root import (
    setup_di_container_from_settings as cordial_container,
)
from cordial_billing.core.application.commands.update_deal_command import (
    UpdatePipedriveDealCommand,
)


class Command(BaseCommand):
    """
    Atualiza o Deal de um CollectionCase existente.

    • Ajusta o valor devido se necessário
    • Move o Deal para a etapa “ADM Verificar” quando apropriado
    • Cria uma Activity explicativa no Pipedrive

    Uso:
        python manage.py update_pipedrive_deal --collection-case-id <UUID>
    """

    help = "Sincroniza valor e/ou etapa de um Deal já existente no Pipedrive"

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
        container = cordial_container(None)
        bus       = container.command_bus()

        result = bus.dispatch(
            UpdatePipedriveDealCommand(
                collection_case_id=opts["collection_case_id"],
            )
        )

        self.stdout.write(self.style.SUCCESS(f"Resultado: {result}"))
