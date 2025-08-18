from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from oralsin_core.adapters.config.composition_root import (
    setup_di_container_from_settings,
)
from oralsin_core.core.application.commands.sync_commands import SyncInadimplenciaCommand

from plugins.django_interface.models import Clinic

WINDOW_DAYS = 3  # ontem-hoje-amanhã cobre ajustes de data & pré-emissão


class Command(BaseCommand):
    """
    Dispara o resync diário para TODAS as clínicas ativas, utilizando
    o SyncInadimplenciaCommand para garantir uma atualização de dados
    consistente e idempotente.
    """

    help = "Sincroniza diariamente os dados de inadimplência de todas as clínicas ativas."

    def handle(self, *args, **options):
        container = setup_di_container_from_settings(None)
        cmd_bus = container.command_bus()

        today = date.today()
        initial = today - timedelta(days=200)
        final = today + timedelta(days=730)

        clinics = Clinic.objects.filter(coverage__active=True).values_list(
            "oralsin_clinic_id", flat=True
        )
        self.stdout.write(
            self.style.NOTICE(
                f"🔄 Iniciando resync para {len(clinics)} clínicas — Janela: {initial} à {final}"
            )
        )

        for cid in clinics:
            try:
                cmd = SyncInadimplenciaCommand(
                    oralsin_clinic_id=cid,
                    data_inicio=initial,
                    data_fim=final,
                    resync=True,  # Sinaliza que é uma atualização e não uma carga inicial
                )
                cmd_bus.dispatch(cmd)
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Resync para clínica {cid} concluído.")
                )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"❌ Falha no resync para clínica {cid}: {e}")
                )

        self.stdout.write(self.style.SUCCESS("🎉 Processo de resync diário finalizado."))