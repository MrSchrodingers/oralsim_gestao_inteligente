from django.core.management.base import BaseCommand, CommandError

from notification_billing.adapters.config.composition_root import container as nb_container
from notification_billing.core.application.commands.sync_commands import BulkScheduleContactsCommand
from plugins.django_interface.models import Clinic


class Command(BaseCommand):
    help = "Agenda em massa (pré-vencimento D-2, 99 se 1º contato inadimplente, e próximos steps) para uma clínica."

    def add_arguments(self, parser):
        parser.add_argument("--clinic-id", required=True, help="PK interna de Clinic (UUID).")

    def handle(self, *args, **opts):
        clinic_id = opts["clinic_id"]

        try:
            Clinic.objects.get(id=clinic_id)
        except Clinic.DoesNotExist:
            raise CommandError(f"Clinic {clinic_id} não encontrada.")

        bus = nb_container.command_bus()
        bus.dispatch(
            BulkScheduleContactsCommand(
                clinic_id=clinic_id,
            )
        )
        self.stdout.write(self.style.SUCCESS(f"bulk_schedule_contacts OK para clinic={clinic_id}"))
