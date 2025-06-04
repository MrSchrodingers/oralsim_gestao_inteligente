from django.core.management.base import BaseCommand
from oralsin_core.adapters.config.composition_root import (
    setup_di_container_from_settings as setup_core_container,
)
from oralsin_core.core.domain.repositories.covered_clinic_repository import (
    CoveredClinicRepository,
)

from notification_billing.adapters.config.composition_root import (
    setup_di_container_from_settings as setup_notification_container,
)
from notification_billing.core.application.commands.sync_commands import (
    BulkScheduleContactsCommand,
)


class Command(BaseCommand):
    """Agenda o **primeiro contato** de cobrança para todas as parcelas *is_current*
    em atraso.  Usa a nova pipeline única de agendamentos.
    """

    help = (
        "Bulk-scheduling de inadimplentes já sincronizados.\n"
        "Se nenhum --clinic-id for passado, roda para TODAS as clínicas cobertas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clinic-id",
            type=int,
            help="ID da clínica na Oralsin (opcional – roda todas se omitido).",
        )
        parser.add_argument(
            "--min-days",
            type=int,
            default=1,
            help="Mínimo de dias de atraso para considerar (default: 1).",
        )

    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        # Containers DI
        core_container         = setup_core_container(None)
        notification_container = setup_notification_container(None)

        covered_repo: CoveredClinicRepository = core_container.covered_clinic_repo()
        command_bus                      = notification_container.command_bus()

        clinic_id = options["clinic_id"]
        min_days  = options["min_days"]

        clinics = (
            [covered_repo.find_by_api_id(clinic_id)]
            if clinic_id
            else covered_repo.list_all()
        )

        for clinic in clinics:
            if clinic is None:
                self.stderr.write(
                    self.style.ERROR(f"Clínica {clinic_id} não encontrada.")
                )
                continue

            self.stdout.write(
                f"🏥  {clinic.name} (oralsin_id={clinic.oralsin_clinic_id}) → agendando…"
            )

            try:
                command_bus.dispatch(
                    BulkScheduleContactsCommand(
                        clinic_id=clinic.oralsin_clinic_id,
                        min_days_overdue=min_days,
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(f"✔️  Concluído para {clinic.name}.")
                )
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"❌  Falha para {clinic.name}: {exc}")
                )
