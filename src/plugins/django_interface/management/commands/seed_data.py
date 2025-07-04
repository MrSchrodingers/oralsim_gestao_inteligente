"""
seed_data.py
────────────────────────────────────────────────────────────────────────────
Cria:
• super_admin (opcional)
• CoveredClinic  ⇢  Clinic (Django)
• usuário da clínica (role="clinic") **usando as credenciais informadas**
• (opcional) sync completo de inadimplência + ajuste de flags de billing

Principais mudanças
───────────────────
1.  Novos argumentos **--clinic-email / --clinic-pass**  
    – permitem enviar login/senha da clínica;
2.  `_create_or_get_clinic_user()` recebe `email`/`password` opcionais;  
    se não vierem, cai no comportamento antigo (slug gerado);
3.  Validação simples: se só um dos dois campos for passado, dispara erro.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from oralsin_core.adapters.config.composition_root import (
    setup_di_container_from_settings,
)
from oralsin_core.core.application.commands.billing_settings_commands import (
    UpdateBillingSettingsCommand,
)
from oralsin_core.core.application.commands.coverage_commands import (
    RegisterCoverageClinicCommand,
)
from oralsin_core.core.application.commands.user_commands import CreateUserCommand
from oralsin_core.core.application.dtos.user_dto import CreateUserDTO

from plugins.django_interface.models import Contract as ContractModel


class Command(BaseCommand):
    help = (
        "Seed dinâmico: cria super_admin, registra a CoveredClinic "
        "e (opcionalmente) sincroniza inadimplência via OralsinCore."
    )

    # ────────────────────────── argumentos CLI ──────────────────────────
    def add_arguments(self, parser) -> None:
        parser.add_argument("--clinic-name",  type=str, help="Nome exato da clínica")
        parser.add_argument("--owner-name",   type=str, help="Nome do responsável")

        # credenciais do super_admin
        parser.add_argument("--admin-email",  default="admin@localhost")
        parser.add_argument("--admin-pass",   default="changeme")
        parser.add_argument("--skip-admin",   action="store_true")

        # credenciais do usuário da clínica
        parser.add_argument("--clinic-email", type=str)
        parser.add_argument("--clinic-pass",  type=str)
        parser.add_argument("--skip-clinic-user", action="store_true")

        parser.add_argument("--min-days-billing", type=int, default=90)
        parser.add_argument("--skip-full-sync",   action="store_true")
        parser.add_argument("--no-schedules",     action="store_true")
        
        parser.add_argument(
            "--resync",
            action="store_true",
            help="Executa em modo atualização para clínicas já existentes",
        )
        parser.add_argument(
            "--window-days",
            type=int,
            default=30,
            help="Janela de dias usada no modo --resync",
        )
        parser.add_argument(
            "--initial-date",
            type=str,
            help="Data inicial (YYYY-MM-DD) para o modo resync",
        )
        parser.add_argument(
            "--final-date",
            type=str,
            help="Data final (YYYY-MM-DD) para o modo resync",
        )

    # ────────────────────────── entry-point ─────────────────────────────
    def handle(self, *args: Any, **opt: Any) -> None:  # noqa: PLR0915
        container = setup_di_container_from_settings(None)
        cmd_bus    = container.command_bus()

        clinic_name: str | None = opt["clinic_name"]
        owner_name:  str | None = opt["owner_name"]

        # super-admin options
        admin_email, admin_pass = opt["admin_email"], opt["admin_pass"]
        skip_admin: bool        = opt["skip_admin"]

        # clinic-user options
        clinic_email: str | None = opt["clinic_email"]
        clinic_pass:  str | None = opt["clinic_pass"]
        skip_clinic_user: bool   = opt["skip_clinic_user"]

        if (clinic_email and not clinic_pass) or (clinic_pass and not clinic_email):
            raise CommandError("--clinic-email e --clinic-pass devem ser usados juntos")

        # ── modo somente-admin ───────────────────────────────────────────
        if not clinic_name:
            if skip_admin:
                self.stdout.write(
                    self.style.WARNING("Nenhuma ação executada. (--clinic-name ausente)")
                )
                return

            self.stdout.write(self.style.NOTICE("🚀 Criando super_admin…"))
            admin_id = self._create_or_get_admin(container, admin_email, admin_pass)
            self.stdout.write(self.style.SUCCESS(f"🎉 super_admin={admin_id}"))
            return

        # se clinic_name foi passado, owner_name é obrigatório
        if not owner_name:
            raise CommandError("--owner-name é obrigatório se --clinic-name for usado")

        # ── SEED COMPLETO ───────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE("🚀 Seed dinâmico completo iniciado…"))

        min_days_billing   = opt["min_days_billing"]
        skip_sync: bool    = opt["skip_full_sync"]
        no_schedules: bool = opt["no_schedules"]
        resync_mode: bool  = opt.get("resync", False)
        window_days: int   = opt.get("window_days", 30)
        initial_date = (
            date.fromisoformat(opt["initial_date"])
            if opt.get("initial_date")
            else None
        )
        final_date = (
            date.fromisoformat(opt["final_date"])
            if opt.get("final_date")
            else None
        )

        with transaction.atomic():
            covered_id, oralsin_id = self._register_coverage(
                container, clinic_name, owner_name
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"🏥 CoveredClinic={covered_id}  OralsinID={oralsin_id}"
                )
            )

            cmd_bus.dispatch(
                UpdateBillingSettingsCommand(
                    clinic_id=str(covered_id),
                    min_days_overdue=min_days_billing,
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"⚙️ BillingSettings.min_days_overdue={min_days_billing}"
                )
            )

            if not skip_admin:
                admin_id = self._create_or_get_admin(container, admin_email, admin_pass)
                self.stdout.write(self.style.SUCCESS(f"👤 super_admin={admin_id}"))

            if not skip_clinic_user:
                clinic_user_id = self._create_or_get_clinic_user(
                    container,
                    clinic_name     = clinic_name,
                    clinic_id       = covered_id,
                    email_override  = clinic_email,
                    password_override = clinic_pass,
                )
                self.stdout.write(self.style.SUCCESS(f"👤 clinic_user={clinic_user_id}"))

        # ── sync inadimplência (opcional) ───────────────────────────────
        self._post_seed_sync(
            container,
            oralsin_id,
            skip_sync,
            no_schedules,
            resync=resync_mode,
            window_days=window_days,
            start_date=initial_date,
            end_date=final_date,
        )
        
        if resync_mode:
            call_command("sync_old_debts", clinic_id=oralsin_id)
            call_command("sync_acordo_activities", clinic_id=oralsin_id)
            call_command("seed_scheduling", clinic_id=oralsin_id)

        self.stdout.write(self.style.SUCCESS("🎉 Seed finalizado com sucesso."))

    # ────────────────────────── helpers ────────────────────────────────
    def _create_or_get_admin(self, container, email: str, password: str) -> uuid.UUID:
        cmd = CreateUserCommand(
            payload=CreateUserDTO(
                email=email,
                password=password,
                name="Super Admin",
                role="admin",
            )
        )
        result = container.command_bus().dispatch(cmd)
        return result.id  # type: ignore

    def _create_or_get_clinic_user(
        self,
        container,
        *,
        clinic_name: str,
        clinic_id: uuid.UUID,
        email_override: str | None,
        password_override: str | None,
    ) -> uuid.UUID:
        """
        Garante User(role='clinic') + vínculo UserClinic.
        Se email/senha forem fornecidos via CLI, usa-os. Caso contrário
        gera `<slug>@oralsin.admin.com.br` / `<slug>@oralsin`.
        """
        if email_override and password_override:
            email, password = email_override, password_override
        else:
            slug  = slugify(clinic_name).replace("-", ".")
            email = f"{slug}@oralsin.admin.com.br"
            password = f"{slug}@oralsin"

        dto = CreateUserDTO(
            email     = email,
            password  = password,
            name      = clinic_name,
            role      = "clinic",
            clinic_id = str(clinic_id),
        )

        try:
            user = container.command_bus().dispatch(CreateUserCommand(payload=dto))
            self.stdout.write(f"➕ Criado clinic-user `{email}`")
        except Exception:
            from plugins.django_interface.models import User as UserModel

            existing = UserModel.objects.filter(email=email).first()
            user = type("X", (), {"id": existing.id})
            self.stdout.write(f"ℹ️ clinic-user `{email}` já existe")
        return user.id  # type: ignore

    def _register_coverage(
        self,
        container,
        clinic_name: str,
        owner_name: str,
    ) -> tuple[uuid.UUID, int]:
        from plugins.django_interface.models import Clinic as ClinicModel

        covered = container.command_bus().dispatch(
            RegisterCoverageClinicCommand(
                clinic_name=clinic_name,
                owner_name=owner_name,
            )
        )
        clinic_obj, _ = ClinicModel.objects.update_or_create(
            oralsin_clinic_id=covered.oralsin_clinic_id,
            defaults={"name": clinic_name},
        )
        return clinic_obj.id, covered.oralsin_clinic_id  # type: ignore

    # ------------------------------------------------------------------
    def _post_seed_sync(  # noqa: PLR0913
        self,
        container,
        oralsin_id: int,
        skip_sync: bool,
        no_schedules: bool,
        *,
        resync: bool = False,
        window_days: int = 30,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> None:
        today = date.today()
        if skip_sync:
            start, end = today - timedelta(days=15), today + timedelta(days=15)
            self.stdout.write(
                self.style.WARNING(f"⚡ --skip-full-sync: {start} → {end}")
            )
        if resync:
            if start_date and end_date:
                start, end = start_date, end_date
            else:
                start, end = (
                    today - timedelta(days=window_days),
                    today + timedelta(days=window_days),
                )
            self.stdout.write(
                self.style.NOTICE(f"⏳ Resync {start} → {end}")
            )
        else:
            start, end = (
                today - timedelta(days=200),
                today + timedelta(days=730),
            )
            self.stdout.write(
                self.style.NOTICE("⏳ Sync completo (datas padrão)…")
            )

        sync_service = container.oralsin_sync_service()
        sync_service.full_sync(
            clinic_id=oralsin_id,
            data_inicio=start,
            data_fim=end,
            no_schedules=no_schedules,
            resync=resync,
        )
        self.stdout.write(self.style.SUCCESS("➡️ Sincronização concluída."))

        # ajuste de flags para ambientes de teste
        if not skip_sync:
            self._adjust_billing_flags(oralsin_id)

    # ------------------------------------------------------------------
    def _adjust_billing_flags(self, oralsin_id: int) -> None:
        self.stdout.write("🌱 Ajustando flags de billing para testes…")
        all_contracts = list(
            ContractModel.objects.filter(clinic__oralsin_clinic_id=oralsin_id)
        )
        random.shuffle(all_contracts)
        half = len(all_contracts) // 2
        billing_ids      = [c.id for c in all_contracts[:half]]
        notification_ids = [c.id for c in all_contracts[half:]]

        ContractModel.objects.filter(id__in=billing_ids).update(
            do_billings=True,
            do_notifications=False,
        )
        ContractModel.objects.filter(id__in=notification_ids).update(
            do_billings=False,
            do_notifications=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Flags Billing/Notification aplicadas ({len(all_contracts)} contratos)"
            )
        )
