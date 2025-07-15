from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from django.core.management.base import BaseCommand
from django.db.models import Max

from plugins.django_interface.models import CollectionCase, Installment


class Command(BaseCommand):
    help = "Aplica mutações no CollectionCase p/ acionar paths do update"

    def add_arguments(self, p):
        p.add_argument("--case-id", required=True)
        p.add_argument(
            "--scenario",
            choices=["value", "stage", "both"],
            required=True,
            help="value = só muda valor; stage = só muda etapa; both = ambos",
        )

    def handle(self, *a, **o):
        case = CollectionCase.objects.get(id=UUID(o["case_id"]))

        # ───────────────────────── VALUE ───────────────────────────
        if o["scenario"] in ("value", "both"):
          next_number = (
              Installment.objects
              .filter(contract=case.contract)
              .aggregate(Max("installment_number"))
              .get("installment_number__max") or 0
          ) + 1

          Installment.objects.create(
              id=uuid4(),
              contract=case.contract,
              contract_version=getattr(case.contract, "contract_version", 1),
              installment_number=next_number,
              oralsin_installment_id=-next_number,
              due_date=date.today() - timedelta(days=1),
              installment_amount=Decimal("250"),
              received=False,
          )

          # ↑ parcela inserida → soma na dívida
          case.amount += Decimal("250")
          case.save(update_fields=["amount"])

        # ───────────────────────── STAGE ───────────────────────────
        if o["scenario"] in ("stage", "both"):
            case.contract.do_billings = False        # atende condição “not do_bill”
            case.contract.save(update_fields=["do_billings"])

        self.stdout.write(self.style.SUCCESS("mutated"))
