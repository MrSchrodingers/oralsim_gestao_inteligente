from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from plugins.django_interface.models import (
    FlowStepConfig,
    Message,
    Patient,
    PatientPhone,
    Payer,
    PayerPhone,
)


class Command(BaseCommand):
    help = (
        "Seed test contacts: atribui e-mail e telefone de teste a todos os pacientes "
        "e seus pagadores associados. Só roda após seed_data, seed_messages e "
        "seed_flow_step_config."
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
        # 1) Pré-checks
        if not FlowStepConfig.objects.exists():
            raise CommandError("❌ Rode antes: manage.py seed_flow_step_config")
        if not Message.objects.exists():
            raise CommandError("❌ Rode antes: manage.py seed_messages")
        if not Patient.objects.exists():
            raise CommandError("❌ Rode antes: manage.py seed_data")

        # 2) Lê valores de e-mail e phone
        test_email = options["email"] or getattr(settings, "TEST_NOTIFICATION_EMAIL", None)
        test_phone = options["phone"] or getattr(settings, "TEST_NOTIFICATION_PHONE", None)
        if not test_email or not test_phone:
            raise CommandError(
                "E-mail ou telefone de teste não informados e não definidos em settings."
            )

        self.stdout.write("🌱 Iniciando seed de contatos de teste para pacientes e pagadores…")
        updated_patients = 0
        
        # Usamos .prefetch_related() para otimizar a busca dos pagadores associados
        for patient in Patient.objects.prefetch_related('payers').all():
            # 3) Atualiza e-mail do Patient
            patient.email = test_email
            patient.contact_name = patient.name
            patient.save(update_fields=["email", "contact_name"])

            # 4) Limpa telefones do Patient e cadastra o de teste
            PatientPhone.objects.filter(patient=patient).delete()
            PatientPhone.objects.create(
                patient=patient,
                phone_number=test_phone,
                phone_type=PatientPhone.Type.MOBILE,  # Usando um choice válido do modelo
            )

            # 5) ✨ NOVO: Atualiza telefones dos Payers (pagadores) associados
            for payer in patient.payers.all():
                PayerPhone.objects.filter(payer=payer).delete()
                PayerPhone.objects.create(
                    payer=payer,
                    phone_number=test_phone,
                    phone_type=PayerPhone.Type.MOBILE, # Usando um choice válido do modelo
                )

            updated_patients += 1
            if updated_patients % 100 == 0:
                self.stdout.write(f"  -> {updated_patients} pacientes processados...")


        self.stdout.write(self.style.SUCCESS(
            f"✅ Seed de teste concluído: {updated_patients} pacientes e seus pagadores associados foram atualizados."
        ))