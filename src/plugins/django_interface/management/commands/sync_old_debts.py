from django.core.management.base import BaseCommand

from cordial_billing.adapters.config.composition_root import (
    setup_di_container_from_settings as cordial_container,
)
from cordial_billing.core.application.commands.collect_commands import (
    SyncOldDebtsCommand,
)


class Command(BaseCommand):
    help = "Cria CollectionCase para parcelas 90+ dias"

    def add_arguments(self, parser):
        parser.add_argument("--clinic-id", required=True, type=str)

    def handle(self, *a, **opts):
        container         = cordial_container(None)
        bus = container.command_bus()
        out = bus.dispatch(
            SyncOldDebtsCommand(
                clinic_id=opts["clinic_id"],
            )
        )
        self.stdout.write(self.style.SUCCESS(str(out)))
