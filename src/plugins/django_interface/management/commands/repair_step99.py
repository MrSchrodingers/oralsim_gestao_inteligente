from django.core.management.base import BaseCommand

from notification_billing.adapters.config.composition_root import setup_di_container_from_settings
from notification_billing.core.application.commands.contact_commands import AdvanceContactStepCommand
from plugins.django_interface.models import ContactSchedule


class Command(BaseCommand):
    help = "Reagenda próximos steps para schedules aprovados no step 99 que ficaram sem pending."

    def handle(self, *args, **opts):
        container = setup_di_container_from_settings(None)
        cmd_bus = container.command_bus()

        fixed = skipped = failed = 0

        qs = (
            ContactSchedule.objects
            .filter(current_step=99, status="approved")
            .only("id", "patient_id", "contract_id", "installment_id")
            .iterator(chunk_size=500)
        )

        for sch in qs:
            try:
                # Se já existe qualquer pending para este patient/contract, pula.
                has_pending = ContactSchedule.objects.filter(
                    patient_id=sch.patient_id,
                    contract_id=sch.contract_id,
                    status="pending",
                ).exists()
                if has_pending:
                    skipped += 1
                    continue

                # Avança a partir do schedule 99 já aprovado
                cmd = AdvanceContactStepCommand(schedule_id=str(sch.id))
                cmd_bus.dispatch(cmd)
                fixed += 1

            except Exception as e:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Falhou p/ {sch.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"Reagendados: {fixed} | Pulados (já tinham pending): {skipped} | Falhas: {failed}"
        ))
