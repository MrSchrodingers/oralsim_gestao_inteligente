from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from oralsin_core.adapters.config.composition_root import setup_di_container_from_settings
from oralsin_core.core.application.commands.register_commands import ResyncClinicCommand

from plugins.django_interface.models import Clinic

WINDOW_DAYS = 3         # ontem-hoje-amanhã cobre ajustes de data & pré-emissão

class Command(BaseCommand):
    help = "Dispara o resync diário para TODAS as clínicas ativas."

    def handle(self, *args, **options):  # noqa: D401
        container = setup_di_container_from_settings(None)
        cmd_bus    = container.command_bus()

        today   = date.today()
        initial  = today - timedelta(days=WINDOW_DAYS)
        final     = today + timedelta(days=WINDOW_DAYS)

        clinics = Clinic.objects.values_list("oralsin_clinic_id", flat=True)
        self.stdout.write(f"🔄 Resync {len(clinics)} clinics — {initial} → {final}")

        for cid in clinics:
            cmd_bus.dispatch(
                ResyncClinicCommand(
                    oralsin_clinic_id = cid,
                    initial_date       = initial,
                    final_date          = final,
                    no_schedules      = True, 
                )
            )
        self.stdout.write(self.style.SUCCESS("✅ Resync completo."))
