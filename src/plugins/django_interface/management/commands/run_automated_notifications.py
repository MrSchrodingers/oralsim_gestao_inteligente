from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand

from notification_billing.adapters.config.composition_root import container as nb_container
from notification_billing.core.application.commands.notification_commands import (
    RunAutomatedNotificationsCommand,
)
from plugins.django_interface.models import Clinic


class Command(BaseCommand):
    help = "Executa processamento automático de notificações para uma clínica (por oralsin_clinic_id)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clinic-id",
            required=True,
            help="UUID de oralsin_clinic_id da clínica para a qual processar notificações automáticas",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Tamanho do lote de schedules a processar por vez (default: 10)",
        )
        parser.add_argument(
            "--only-pending",
            action="store_true",
            default=False,
            help="Se informado, processa apenas schedules com status PENDING (default: todos)",
        )
        parser.add_argument(
            "--channel",
            help="Filtra por canal específico (sms, whatsapp, email, phonecall)",
        )

    def handle(self, *args, **opts):
        oralsin_id = opts["clinic_id"]
        try:
            clinic = Clinic.objects.get(oralsin_clinic_id=oralsin_id)
        except ObjectDoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f"Clinic with oralsin_clinic_id={oralsin_id} not found."
                )
            )
            return

        # aqui usamos a PK interna (clinic.id) no comando
        cmd = RunAutomatedNotificationsCommand(
            clinic_id=str(clinic.id),
            batch_size=opts["batch_size"],
            only_pending=opts["only_pending"],
            channel=opts.get("channel"),
        )
        bus = nb_container.command_bus()
        result = bus.dispatch(cmd)

        self.stdout.write(self.style.SUCCESS(f"Resultado run_automated: {result}"))
