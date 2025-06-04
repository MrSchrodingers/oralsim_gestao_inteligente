from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from plugins.django_interface.models import (
    FlowStepConfig,
    Message,
    Patient,
    PatientPhone,
)


class Command(BaseCommand):
    help = (
        "Seed test contacts: atribui email e telefone de teste a todos os pacientes. "
        "Só roda após seed_data, seed_messages e seed_flow_step_config."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            help="E-mail de teste a usar (ex: seu@teste.com). Se não informado, usa settings.TEST_NOTIFICATION_EMAIL.",
        )
        parser.add_argument(
            "--phone",
            help="Telefone de teste a usar (ex: +551199999999). Se não informado, usa settings.TEST_NOTIFICATION_PHONE.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) pré-checks
        if not FlowStepConfig.objects.exists():
            raise CommandError("❌ Rode antes: manage.py seed_flow_step_config")
        if not Message.objects.exists():
            raise CommandError("❌ Rode antes: manage.py seed_messages")
        if not Patient.objects.exists():
            raise CommandError("❌ Rode antes: manage.py seed_data")

        # 2) lê valores de email e phone
        test_email = options["email"] or getattr(settings, "TEST_NOTIFICATION_EMAIL", None)
        test_phone = options["phone"] or getattr(settings, "TEST_NOTIFICATION_PHONE", None)
        if not test_email or not test_phone:
            raise CommandError(
                "E-mail ou telefone de teste não informados e não definido em settings."
            )

        self.stdout.write("🌱 Iniciando seed de contatos de teste…")
        updated = 0

        for patient in Patient.objects.all():
            # sobrescreve email do Patient
            patient.email = test_email
            patient.contact_name = patient.name
            patient.save(update_fields=["email", "contact_name"])

            # limpa telefones e cadastra o de teste
            PatientPhone.objects.filter(patient=patient).delete()
            PatientPhone.objects.create(
                patient=patient,
                phone_number=test_phone,
                phone_type="test",  # ou outro choice válido
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ Seed de teste concluído: {updated} pacientes atualizados."
        ))
