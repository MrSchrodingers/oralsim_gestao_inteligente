from django.core.management.base import BaseCommand

from cordial_billing.adapters.config.composition_root import setup_di_container_from_settings
from cordial_billing.core.application.commands.sync_acordo_activity_commands import (
    SyncAcordoActivitiesCommand,
)
from plugins.django_interface.models import PipeboardActivitySent


class Command(BaseCommand):
    help = "Sincroniza atividades 'acordo_fechado'"

    def add_arguments(self, parser):
        parser.add_argument("--clinic-id", required=True, type=str)

    def handle(self, *a, **opts):
        container = setup_di_container_from_settings(None)
        bus = container.command_bus()

        last = (
            PipeboardActivitySent.objects
            .order_by("-activity_id")
            .values_list("activity_id", flat=True)
            .first() or 0
        )

        cmd = SyncAcordoActivitiesCommand(
            clinic_id=opts["clinic_id"],
            after_id=last,
            batch_size=500,
        )
        result = bus.dispatch(cmd)
        self.stdout.write(self.style.SUCCESS(f"Pipeline concluído: {result}"))

