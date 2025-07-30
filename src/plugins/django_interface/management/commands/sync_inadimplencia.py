from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandParser
from oralsin_core.adapters.config.composition_root import (
    setup_di_container_from_settings,
)
from oralsin_core.core.application.commands.sync_commands import (
        SyncInadimplenciaCommand,
    )


class Command(BaseCommand):
    """
    Executa a sincronização de inadimplência para UMA ÚNICA clínica, 
    permitindo especificar a janela de datas. Projetado para ser chamado
    por tarefas assíncronas (Celery) ou para execuções manuais.
    """

    help = "Sincroniza os dados de inadimplência para uma clínica específica."

    def add_arguments(self, parser: CommandParser):
        """Define os argumentos que o comando aceita pela linha de comando."""
        parser.add_argument(
            "--oralsin-clinic-id",
            required=True,
            type=str,
            help="UUID (oralsin_clinic_id) da clínica a ser sincronizada.",
        )
        parser.add_argument(
            "--data-inicio",
            type=date.fromisoformat,
            help="Data de início da janela de sincronização (formato: YYYY-MM-DD). Default: Ontem.",
        )
        parser.add_argument(
            "--data-fim",
            type=date.fromisoformat,
            help="Data de fim da janela de sincronização (formato: YYYY-MM-DD). Default: Amanhã.",
        )
        parser.add_argument(
            '--no-resync',
            action='store_false',
            dest='resync',
            help="Use esta flag para indicar que é uma carga inicial, não uma atualização."
        )
        parser.set_defaults(resync=True)


    def handle(self, *args, **options):
        """Lógica principal do comando."""
        container = setup_di_container_from_settings(None)
        cmd_bus = container.command_bus()

        clinic_id = options["oralsin_clinic_id"]
        is_resync = options["resync"]
        
        # Define as datas padrão se não forem fornecidas
        today = date.today()
        initial_date = options["data_inicio"] or (today - timedelta(days=1))
        final_date = options["data_fim"] or (today + timedelta(days=1))

        self.stdout.write(
            self.style.NOTICE(
                f"▶️  Iniciando sincronização para a clínica {clinic_id}..."
            )
        )
        self.stdout.write(
            f"   - Janela de dados: {initial_date.isoformat()} a {final_date.isoformat()}"
        )
        self.stdout.write(f"   - Modo Resync: {'ATIVADO' if is_resync else 'DESATIVADO'}")
        
        try:
            cmd = SyncInadimplenciaCommand(
                oralsin_clinic_id=clinic_id,
                data_inicio=initial_date,
                data_fim=final_date,
                resync=is_resync,
            )
            cmd_bus.dispatch(cmd)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Sincronização para a clínica {clinic_id} concluída com sucesso."
                )
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(
                    f"❌ Falha crítica na sincronização para a clínica {clinic_id}: {e}"
                )
            )
