# tests/test_notification_flow.py
"""
Test-suite de ponta-a-ponta para o pipeline de cobrança / notificações.

• Usa exclusivamente dados vindos dos *seeds* oficiais + comandos
  de bulk-scheduling — nada é “inventado” durante o teste.

• Suporta dois modos de execução:
    1. **Mock** – notificadores são “monkey-patched”; nada é disparado,
       porém a lógica de domínio é validada.
    2. **Real** – define `REAL_NOTIFIER_FLOW=true` e garante que os
       credentials de produção estejam presentes; mensagens serão
       enviadas de verdade.

Requisitos de ambiente:
---------------------------------------------------------------------
* Todas as migrations aplicadas.
* Comandos `seed_flow_step_config`, `seed_messages`, `seed_data`,
  `seed_test_contatcs`   disponíveis no `manage.py`.
* Variáveis de ambiente para o modo real (gateway SMS, WhatsApp,
  e-mail, etc.) — opcional.
"""

from __future__ import annotations

import os
from datetime import timedelta

import structlog
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from notification_billing.adapters.config.composition_root import (
    container as nb_container,
)
from notification_billing.core.application.services.notification_service import (
    NotificationFacadeService,
)
from plugins.django_interface.models import (
    Clinic,
    ContactHistory,
    ContactSchedule,
    Contract,
    FlowStepConfig,
    Installment,
    Message,
    Patient,
)

# util interno de testes
from tests.helpers.patch_notifiers_if_mock import patch_notifiers_if_mock


logger = structlog.get_logger(__name__)


class NotificationFlowTests(TestCase):
    """
    Integra o domínio de cobrança (agendamento → envio → histórico).

    Cada teste parte de um banco “semeado” com registros reais
    (clínica *Bauru*, pacientes, contratos e parcelas).
    """

    # ----------------------------------------------------------------─  class-level

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Ativa modo MOCK caso as libs externas não estejam disponíveis
        cls._notifier_patches = patch_notifiers_if_mock()
        cls._mock_mode = bool(cls._notifier_patches)
        cls._real_mode = (
            os.getenv("REAL_NOTIFIER_FLOW", "false").lower() == "true"
            and not cls._mock_mode
        )

        logger.info("[TEST-SETUP] mock_mode=%s real_mode=%s", cls._mock_mode, cls._real_mode)

        # façade de alto nível utilizada pelos testes
        cls.facade: NotificationFacadeService = nb_container.notification_service()

    @classmethod
    def tearDownClass(cls):
        for p in cls._notifier_patches:
            p.stop()
        super().tearDownClass()

    # ----------------------------------------------------------------─  data-set-up-once

    @classmethod
    def setUpTestData(cls):
        """
        Executa uma única vez para toda a classe.

        * carrega configs de fluxo
        * mensagem padrão
        * dados da clínica Bauru (+ sync light)
        * pacientes “seed” para disparos
        """
        logger.info("[TEST-DATA] resetando tabelas principais")

        for model in (ContactSchedule, ContactHistory, Installment, Patient):
            model.objects.all().delete()

        call_command("seed_flow_step_config", verbosity=0)
        call_command("seed_messages", verbosity=0)
        call_command(
            "seed_data",
            clinic_name="Bauru",
            admin_email="matheus@admin.com",
            admin_pass="matheus@admin",
            verbosity=0,
        )
        call_command(
            "seed_test_contatcs",
            email="mrschrodingers@gmail.com",
            phone="5543991938235",
            verbosity=1,
        )

        # garante que o step 1 tenha canais ativos e cooldown 0 para acelerar o teste
        FlowStepConfig.objects.update_or_create(
            step_number=1,
            defaults={
                "channels": ["whatsapp", "sms"],
                "cooldown_days": 0,
                "active": True,
                "description": "Step 1",
            },
        )

    # ----------------------------------------------------------------─  helpers

    def _get_seed_patient_contract_clinic(self) -> tuple[Patient, Contract, Clinic]:
        """Retorna 1 paciente, seu contrato ativo e respectiva clínica."""
        patient = Patient.objects.filter(contracts__status="ativo").first()
        self.assertIsNotNone(
            patient,
            "Nenhum paciente ativo foi criado pelo seed_data.",
        )

        contract = patient.contracts.filter(status="ativo").first()
        self.assertIsNotNone(
            contract,
            f"Paciente {patient.id} não possui contrato ativo.",
        )

        clinic = contract.clinic
        self.assertIsNotNone(
            clinic,
            f"Contrato {contract.id} não possui clínica vinculada.",
        )
        return patient, contract, clinic

    # ----------------------------------------------------------------─  per-test-setup

    def setUp(self):
        """
        Para **cada** teste:

        1. Garante que exista uma *installment* atual (`is_current=True`)
           vencida ontem.
        2. Executa o *bulk-scheduler* para gerar (ou idempotentemente
           reaproveitar) os `ContactSchedule` pendentes.
        """
        patient, contract, clinic = self._get_seed_patient_contract_clinic()

        # parcela “current” vencida
        inst, _ = Installment.objects.get_or_create(
            contract=contract,
            is_current=True,
            defaults={
                "installment_number": 1,
                "due_date": timezone.now().date() - timedelta(days=1),
                "installment_amount": 100.00,
                "received": False,
                "installment_status": "pending_payment",
            },
        )
        inst.due_date = timezone.now().date() - timedelta(days=1)
        inst.received = False
        inst.save(update_fields=["due_date", "received"])

        # (re)executa o scheduler idempotente
        call_command(
            "seed_scheduling",
            clinic_id=clinic.oralsin_clinic_id,
            min_days=1,
            verbosity=0,
        )

    # ----------------------------------------------------------------─  testes

    def test_fullsync_creates_auto_schedules(self):
        """`seed_scheduling` deve ter gerado ao menos 1 schedule pendente."""
        self.assertTrue(Patient.objects.exists(), "Nenhum Patient foi criado.")
        self.assertTrue(ContactSchedule.objects.exists(), "Nenhum ContactSchedule criado.")
        self.assertGreater(
            ContactSchedule.objects.filter(status=ContactSchedule.Status.PENDING).count(),
            0,
            "Esperava ContactSchedule pendente após seed_scheduling.",
        )

    # ---------- modo REAL (somente se habilitado) ---------------------

    def test_real_mode_manual_send(self):
        """Dispara *manual_send* real (ou falha se não habilitado)."""
        if not self._real_mode:
            self.skipTest("Modo REAL não habilitado.")

        patient, contract, clinic = self._get_seed_patient_contract_clinic()

        sched = (
            ContactSchedule.objects.filter(
                patient=patient,
                contract=contract,
                status=ContactSchedule.Status.PENDING,
            )
            .order_by("current_step")
            .first()
        )
        self.assertIsNotNone(
            sched,
            "Nenhum ContactSchedule pendente encontrado para manual_send.",
        )
        self.assertIsNotNone(sched.channel, "Schedule não possui canal definido.")

        # tenta pegar mensagem específica da clínica; senão, global
        msg = (
            Message.objects.filter(
                step=sched.current_step,
                clinic=clinic,
                type=sched.channel,
            ).first()
            or Message.objects.filter(
                step=sched.current_step, clinic=None, type=sched.channel
            ).first()
        )
        self.assertIsNotNone(
            msg,
            f"Nenhuma Message encontrada (step={sched.current_step}, canal={sched.channel}).",
        )

        # dispara
        self.facade.send_manual(
            patient_id=str(patient.id),
            contract_id=str(contract.id),
            channel=sched.channel,
            message_id=str(msg.id),
        )

        self.assertTrue(
            ContactHistory.objects.filter(
                patient_id=patient.id,
                contract_id=contract.id,
                contact_type=sched.channel,
                message_id=msg.id,
            ).exists(),
            "ContactHistory não registrado após manual_send.",
        )

    def test_real_mode_automated_run(self):
        """`run_automated` deve processar schedules pendentes (modo REAL)."""
        if not self._real_mode:
            self.skipTest("Modo REAL não habilitado.")

        _, _, clinic = self._get_seed_patient_contract_clinic()

        pendentes = ContactSchedule.objects.filter(
            clinic=clinic,
            status=ContactSchedule.Status.PENDING,
            scheduled_date__lte=timezone.now(),
        ).count()
        self.assertGreater(pendentes, 0, "Nenhum schedule pendente disponível.")

        self.facade.run_automated(clinic_id=str(clinic.id), batch_size=2)

        self.assertTrue(
            ContactHistory.objects.exists(),
            "Nenhum ContactHistory criado após run_automated.",
        )

    # ---------- modo MOCK / genérico ---------------------------------

    def test_pending_schedules_are_notified_on_automated_run(self):
        """
        Em mock ou real, executar *run_automated* deve registrar histórico
        para ao menos parte dos schedules pendentes.
        """
        _, _, clinic = self._get_seed_patient_contract_clinic()

        before = ContactSchedule.objects.filter(
            clinic=clinic,
            status=ContactSchedule.Status.PENDING,
            scheduled_date__lte=timezone.now(),
        ).count()
        self.assertGreater(before, 0, "Nenhum schedule pendente para teste.")

        self.facade.run_automated(clinic_id=str(clinic.id), batch_size=10)

        notified = ContactHistory.objects.filter(clinic=clinic).count()
        self.assertGreater(
            notified,
            0,
            "Nenhum ContactHistory criado após run_automated.",
        )
