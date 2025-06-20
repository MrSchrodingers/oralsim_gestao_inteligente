from django.core.management.base import BaseCommand

from notification_billing.adapters.config.composition_root import container
from notification_billing.core.application.commands.letter_commands import SendPendingLettersCommand


class Command(BaseCommand):
    help = "Envia um lote de cartas de notificação pendentes para um destinatário fixo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clinic-id",
            required=True,
            help="UUID da clínica para a qual processar as cartas pendentes.",
        )

    def handle(self, *args, **options):
        clinic_id = options["clinic_id"]
        self.stdout.write(self.style.NOTICE(f"Iniciando envio em lote de cartas para a clínica {clinic_id}..."))

        command = SendPendingLettersCommand(clinic_id=clinic_id)
        command_bus = container.command_bus()
        
        try:
            command_bus.dispatch(command)
            self.stdout.write(self.style.SUCCESS("Processo de envio em lote finalizado com sucesso."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Ocorreu um erro durante o envio em lote: {e}"))