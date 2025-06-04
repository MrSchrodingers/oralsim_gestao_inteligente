
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from oralsin_core.adapters.config.composition_root import setup_di_container_from_settings
from oralsin_core.core.application.commands.coverage_commands import RegisterCoverageClinicCommand
from oralsin_core.core.application.commands.user_commands import CreateUserCommand
from oralsin_core.core.application.dtos.user_dto import CreateUserDTO


class Command(BaseCommand):
    help = (
        "Seed dinâmico: cria super_admin, registra a CoveredClinic "
        "e (opcionalmente) sincroniza inadimplência via OralsinCore."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--clinic-name",
            type=str,
            required=True,
            help='Nome exato da clínica na Oralsin (ex.: "Bauru")',
        )
        parser.add_argument(
            "--admin-email",
            type=str,
            default="admin@localhost",
            help="E-mail do super_admin",
        )
        parser.add_argument(
            "--admin-pass",
            type=str,
            default="changeme",
            help="Senha do super_admin",
        )
        parser.add_argument(
            "--skip-full-sync",
            action="store_true",
            help="Usa intervalo curto de datas para sync de teste rápido.",
        )
        parser.add_argument(
            "--no-schedules",
            action="store_true",
            help="Não agenda ContactSchedule durante o sync (apenas persiste core).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # inicializa o container DI do core
        container = setup_di_container_from_settings(None)

        clinic_name: str = options["clinic_name"]
        admin_email: str = options["admin_email"]
        admin_pass: str = options["admin_pass"]
        skip_sync: bool = options["skip_full_sync"]
        no_schedules: bool = options["no_schedules"]

        self.stdout.write(self.style.NOTICE("🚀 Seed dinâmico iniciado…"))

        # 1️⃣ Bloco transacional: super-admin + cobertura
        with transaction.atomic():
            admin_id = self._create_or_get_admin(container, admin_email, admin_pass)
            covered_id, oralsin_id = self._register_coverage(container, clinic_name)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Admin={admin_id}  CoveredClinic={covered_id}  OralsinID={oralsin_id}"
                )
            )

        # 2️⃣ Sincronização de inadimplência
        today = date.today()
        if skip_sync:
            start = today - timedelta(days=15)
            end = today + timedelta(days=15)
            self.stdout.write(
                self.style.WARNING(
                    f"⚡ --skip-full-sync: sincronizando {start} → {end}"
                )
            )
            self._run_sync(container, oralsin_id, start, end, no_schedules=no_schedules)
        else:
            self.stdout.write(
                self.style.NOTICE(
                    "⏳ sync completo: usando datas padrão (pode demorar)..."
                )
            )
            start = today - timedelta(days=200)
            end = today + timedelta(days=730)
            self._run_sync(container, oralsin_id, start, end, no_schedules=no_schedules)

        self.stdout.write(self.style.SUCCESS("🎉 Seed finalizado com sucesso."))

    def _create_or_get_admin(
        self,
        container,
        email: str,
        password: str,
    ) -> uuid.UUID:
        cmd = CreateUserCommand(
            payload=CreateUserDTO(
                email=email,
                password=password,
                name="Super Admin Seed",
                role="admin",
            )
        )
        result = container.command_bus().dispatch(cmd)
        self.stdout.write(f"👤 super_admin ID={result.id}")
        return result.id  # type: ignore

    def _register_coverage(
        self,
        container,
        clinic_name: str,
    ) -> tuple[uuid.UUID, int]:
        cmd = RegisterCoverageClinicCommand(clinic_name=clinic_name)
        covered = container.command_bus().dispatch(cmd)
        self.stdout.write(
            f"🏥 CoveredClinic '{clinic_name}' registrada "
            f"(oralsin_id={covered.oralsin_clinic_id}  uuid={covered.id})"
        )
        return covered.id, covered.oralsin_clinic_id  # type: ignore

    def _run_sync(
        self,
        container,
        oralsin_id: int,
        start: date | None,
        end: date | None,
        no_schedules: bool,
    ) -> None:
        sync_service = container.oralsin_sync_service()
        try:
            sync_service.full_sync(
                clinic_id=oralsin_id,
                data_inicio=start,
                data_fim=end,
                no_schedules=no_schedules,
            )
            self.stdout.write(self.style.SUCCESS("➡️ Sincronização concluída."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erro no sync: {e}"))
            raise
