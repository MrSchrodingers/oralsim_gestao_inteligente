from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from oralsin_core.adapters.config.composition_root import setup_di_container_from_settings
from oralsin_core.core.application.commands.billing_settings_commands import UpdateBillingSettingsCommand
from oralsin_core.core.application.commands.coverage_commands import RegisterCoverageClinicCommand
from oralsin_core.core.application.commands.user_commands import CreateUserCommand
from oralsin_core.core.application.dtos.user_dto import CreateUserDTO

from plugins.django_interface.models import CoveredClinic
from plugins.django_interface.models import User as UserModel


class Command(BaseCommand):
    help = (
        "Seed dinâmico: cria super_admin, CoveredClinic e usuário de clínica, além de configurações de billing e sync.\n"
        "ATENÇÃO: pode ser destrutivo se usado sem --force."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--clinic-name", type=str, help="Nome exato da clínica para criar ou atualizar.")
        parser.add_argument("--owner-name",  type=str, help="Nome do proprietário/responsável.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Força execução mesmo se já houver clínicas (use com cuidado).",
        )
        parser.add_argument("--admin-email", default="admin@localhost", help="Email do super_admin.")
        parser.add_argument("--admin-pass",  default="changeme", help="Senha do super_admin.")
        parser.add_argument("--skip-admin",  action="store_true", help="Não cria/atualiza o super_admin.")
        parser.add_argument("--clinic-email", type=str, help="Email para o usuário da clínica.")
        parser.add_argument("--clinic-pass",  type=str, help="Senha para o usuário da clínica.")
        parser.add_argument("--skip-clinic-user", action="store_true", help="Não cria/atualiza o usuário da clínica.")
        parser.add_argument(
            "--min-days-billing", type=int, default=90,
            help="Define min_days_overdue para billing settings."
        )
        parser.add_argument("--skip-full-sync", action="store_true", help="Pula sincronização completa de inadimplência.")
        parser.add_argument("--no-schedules",   action="store_true", help="Sincroniza sem agendamentos.")
        parser.add_argument(
            "--resync", action="store_true",
            help="Roda sync em modo resync para intervalo definido."
        )
        parser.add_argument("--window-days", type=int, default=30, help="Janela de dias para resync (antes e depois).")
        parser.add_argument("--initial-date", type=str, help="Data inicial YYYY-MM-DD para resync.")
        parser.add_argument("--final-date",   type=str, help="Data final YYYY-MM-DD para resync.")


    @transaction.atomic
    def handle(self, *args: Any, **opt: Any) -> None:
        self.stdout.write(self.style.WARNING("--- INICIANDO SEED DINÂMICO ---"))

        if CoveredClinic.objects.exists() and not opt["force"]:
            raise CommandError("Já existem clínicas no banco. Para reexecutar use --force (cautela).")

        if (opt["clinic_email"] and not opt["clinic_pass"]) or (opt["clinic_pass"] and not opt["clinic_email"]):
            raise CommandError("--clinic-email e --clinic-pass devem ser usados juntos.")

        container = setup_di_container_from_settings(None)
        cmd_bus = container.command_bus()

        clinic_name = opt.get("clinic_name")
        owner_name  = opt.get("owner_name")

        if not clinic_name:
            if opt["skip_admin"]:
                self.stdout.write(self.style.WARNING("Nenhuma ação: faltou --clinic-name e --skip-admin definido."))
                return
            self.stdout.write(self.style.NOTICE("🚀 Criando/atualizando super_admin…"))
            admin_id = self._create_or_get_user(cmd_bus, role="admin", email=opt["admin_email"], password=opt["admin_pass"], name="Super Admin")
            self.stdout.write(self.style.SUCCESS(f"🎉 super_admin id={admin_id}"))
            return

        if not owner_name:
            raise CommandError("--owner-name obrigatório quando --clinic-name é usado.")

        self.stdout.write(self.style.NOTICE("🚀 Seed completo iniciado…"))

        # 1. Registrar cobertura da clínica (core)
        result = cmd_bus.dispatch(RegisterCoverageClinicCommand(
            clinic_name=clinic_name, owner_name=owner_name
        ))
        self.stdout.write(self.style.SUCCESS(f"🏥 Clínica registrada no Core (id={result.clinic_id})"))

        # 2. Atualizar ou criar o modelo local CoveredClinic para referência
        covered, _ = CoveredClinic.objects.update_or_create(
            oralsin_clinic_id=result.oralsin_clinic_id,
            defaults={"name": clinic_name, "owner_name": owner_name},
        )
        self.stdout.write(self.style.SUCCESS(f"🔗 Modelo local CoveredClinic sincronizado (id={covered.id})"))

        # 3. Configurar billing usando o ID do domínio (result.clinic_id)
        cmd_bus.dispatch(UpdateBillingSettingsCommand(
            clinic_id=str(result.clinic_id),
            min_days_overdue=opt["min_days_billing"],
        ))
        self.stdout.write(self.style.SUCCESS(f"⚙️ BillingSettings.min_days_overdue={opt['min_days_billing']}"))

        # Cria super_admin se necessário
        if not opt["skip_admin"]:
            self._create_or_get_user(cmd_bus, role="admin", email=opt["admin_email"], password=opt["admin_pass"], name="Super Admin")

        # Cria usuário da clínica
        if not opt["skip_clinic_user"] and opt.get("clinic_email"):
            self._create_or_get_user(
                cmd_bus,
                role="clinic",
                email=opt["clinic_email"],
                password=opt["clinic_pass"],
                name=clinic_name,
                clinic_id=str(result.clinic_id),
            )

        # Sincronização de inadimplência
        self._post_seed_sync(
            container,
            clinic_id=result.oralsin_clinic_id,
            skip_sync=opt["skip_full_sync"],
            no_schedules=opt["no_schedules"],
            resync=opt["resync"],
            window_days=opt["window_days"],
            start_str=opt.get("initial_date"),
            end_str=opt.get("final_date"),
        )

        self.stdout.write(self.style.SUCCESS("🎉 Seed finalizado com sucesso."))

    def _create_or_get_user(self, cmd_bus, role: str, email: str, password: str, name: str, clinic_id: str | None = None) -> uuid.UUID:  # noqa: PLR0913
        dto = CreateUserDTO(
            email=email, password=password, name=name, role=role, clinic_id=clinic_id
        )
        try:
            result = cmd_bus.dispatch(CreateUserCommand(payload=dto))
            self.stdout.write(self.style.SUCCESS(f"✅ Usuário '{email}' criado (role={role})."))
            return result.id
        except Exception:
            existing = UserModel.objects.filter(email=email).first()
            self.stdout.write(self.style.NOTICE(f"ℹ️ Usuário '{email}' já existe."))
            return existing.id

    def _post_seed_sync(self, container, clinic_id: int, skip_sync: bool, no_schedules: bool, *, resync: bool, window_days: int, start_str: str | None, end_str:   str | None) -> None:  # noqa: PLR0913
        today = date.today()
        if skip_sync:
            start, end = today - timedelta(days=15), today + timedelta(days=15)
            self.stdout.write(self.style.WARNING(f"--skip-full-sync: pulando sync (janela {start} → {end})"))
        elif resync:
            if start_str and end_str:
                start = date.fromisoformat(start_str)
                end   = date.fromisoformat(end_str)
            else:
                start = today - timedelta(days=window_days)
                end   = today + timedelta(days=window_days)
            self.stdout.write(self.style.NOTICE(f"⏳ Resync {start} → {end}"))
        else:
            start = today - timedelta(days=200)
            end   = today + timedelta(days=730)
            self.stdout.write(self.style.NOTICE("⏳ Sync completo (datas padrão)…"))

        sync_service = container.oralsin_sync_service()
        sync_service.full_sync(
            clinic_id=clinic_id,
            data_inicio=start,
            data_fim=end,
            no_schedules=no_schedules,
            resync=resync,
        )
        self.stdout.write(self.style.SUCCESS("➡️ Sincronização concluída."))

        if resync:
            call_command("sync_old_debts", clinic_id=clinic_id)
            call_command("sync_acordo_activities", clinic_id=clinic_id)
            call_command("seed_scheduling", clinic_id=clinic_id)