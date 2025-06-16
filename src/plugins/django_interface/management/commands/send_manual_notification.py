from django.core.management.base import BaseCommand

from notification_billing.adapters.config.composition_root import container as nb_container
from notification_billing.core.application.commands.notification_commands import SendManualNotificationCommand


class Command(BaseCommand):
    help = "Dispara manualmente uma notificação para um paciente/contrato."

    def add_arguments(self, parser):
        parser.add_argument(
            "--patient-id",
            required=True,
            help="UUID do paciente (campo Patient.id)",
        )
        parser.add_argument(
            "--contract-id",
            required=True,
            help="UUID do contrato (campo Contract.id)",
        )
        parser.add_argument(
            "--channel",
            required=True,
            choices=["sms", "whatsapp", "email", "phonecall"],
            help="Canal de envio",
        )
        parser.add_argument(
            "--message-id",
            required=True,
            help="ID da Message (campo Message.id) a usar no envio",
        )

    def handle(self, *args, **opts):
        bus = nb_container.command_bus()

        cmd = SendManualNotificationCommand(
            patient_id=opts["patient_id"],
            contract_id=opts["contract_id"],
            channel=opts["channel"],
            message_id=opts["message_id"],
        )
        result = bus.dispatch(cmd)
        self.stdout.write(self.style.SUCCESS(f"Resultado send_manual: {result}"))
