from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from functools import cached_property
from typing import Any

from django.conf import settings

from plugins.django_interface.models import ClinicPhone, CollectionCase, Installment

CF: dict[str, str] = settings.PIPEDRIVE_CF_MAP


class PipedriveDealPayloadBuilder:
    """Cria o corpo JSON para /deals (create ou update)."""

    OWNER_ID    = 22346271     # usuário Cordial
    PIPELINE_ID = 3
    STAGE_ID    = 15
    ENUM_PATIENT = 28          # valor “Paciente” no campo Tipo

    def __init__(self, case: CollectionCase) -> None:
        self.case     = case
        self.patient  = case.patient
        self.clinic   = case.clinic
        self.contract = case.contract

    # ───────────────────────── API pública ──────────────────────────
    def build(self) -> dict[str, Any]:
        title = (
            f"{self.patient.cpf} - {self.patient.name}"
            if self.patient.cpf else self.patient.name
        )[:255]

        # ---- valores base do deal ---------------------------------
        payload: dict[str, Any] = {
            "title":    title,
            "value":    float(self.case.amount),
            "currency": "BRL",
            "owner_id":     self.OWNER_ID,
            "pipeline_id":  self.PIPELINE_ID,
            "stage_id":     self.STAGE_ID,
            "expected_close_date": (_dt.date.today() + _dt.timedelta(days=30)).isoformat(),
        }

        # ---- custom-fields ----------------------------------------
        custom = {
            CF["clinic_name"]:     self.clinic.name,
            CF["clinic_city"]:     self._clinic_city(),
            CF["clinic_cnpj"]:     self.clinic.cnpj,
            CF["clinic_address"]:  self._clinic_address(),
            CF["clinic_phone"]:    self._clinic_phone(),

            CF["patient_type"]:        self.ENUM_PATIENT,
            CF["patient_first_name"]:  self._first_name(),
            CF["patient_last_name"]:   self._last_name(),
            CF["patient_cpf"]:         self.patient.cpf,
            CF["patient_address"]:     self._patient_address(),
            CF["patient_payment_method"]: self._payment_method(),
            CF["patient_status"]:         self.contract.status,

            CF["contract_numbers"]:        self._contract_code(),
            CF["oldest_due_date"]:         self._oldest_due(),
            CF["newest_due_date"]:         self._newest_due(),
            CF["overdue_count"]:           self._overdue_count(),
            CF["future_count"]:            self._future_count(),
            CF["total_debt"]:              self._money(self._total_debt()),
            CF["future_value"]:            self._money(self._future_value()),
            CF["overdue_value_plain"]:     self._money(self._overdue_plain()),
            # CF["overdue_value_interest"]:  self._money(self.case.amount),

            CF["processing_date"]: _dt.date.today().isoformat(),
            CF["cleaned_flag"]:    47,  # “Não”
        }

        custom = {
            k: v
            for k, v in custom.items()
            if k                                       # key não vazia
            and v not in (None, "", [])                # value não vazio
        }
        return {**payload, "custom_fields": custom}

    # ───────────────────────── helpers ──────────────────────────────
    @staticmethod
    def _money(amount: Decimal | float | int) -> dict[str, Any]:
        return {"value": float(amount), "currency": "BRL"}

    def _clinic_city(self) -> str | None:
        """
        Tenta cidade na sequência:
        1) clinic.city
        2) clinic.data.address.city
        """
        if getattr(self.clinic, "city", None):
            return self.clinic.city
        data = getattr(self.clinic, "data", None)
        return data.address.city if data and data.address else None
    
    def _contract_code(self) -> str:
        if not self.contract.oralsin_contract_id:
            return ""
        ver = (f" v.{self.contract.contract_version}"
               if self.contract.contract_version else "")
        return f"{self.contract.oralsin_contract_id}{ver}"

    # ---------- parcelas -------------------------------------------
    @cached_property
    def _installments(self):
        return (
            getattr(self.contract, "prefetched_installments", None)
            or Installment.objects.filter(contract_id=self.contract.id)
        )

    def _oldest_due(self):
        inst = min(self._installments, key=lambda i: i.due_date, default=None)
        return inst.due_date.isoformat() if inst else None

    def _newest_due(self):
        inst = max(self._installments, key=lambda i: i.due_date, default=None)
        return inst.due_date.isoformat() if inst else None

    def _overdue_count(self):
        today = _dt.date.today()
        return sum(1 for i in self._installments if not i.received and i.due_date < today)

    def _future_count(self):
        today = _dt.date.today()
        return sum(1 for i in self._installments if not i.received and i.due_date >= today)

    def _sum(self, *, future: bool | None = None):
        today = _dt.date.today()
        def cond(i):
            if i.received:
                return False
            if future is None:
                return True
            return i.due_date >= today if future else i.due_date < today
        return sum((i.installment_amount for i in self._installments if cond(i)), Decimal())

    def _total_debt(self):    return self._sum()
    def _future_value(self):  return self._sum(future=True)
    def _overdue_plain(self): return self._sum(future=False)

    # ---------- paciente -------------------------------------------
    def _first_name(self):
        return (self.patient.name or "").split()[0]

    def _last_name(self):
        parts = (self.patient.name or "").split()
        return " ".join(parts[1:]) if len(parts) > 1 else ""

    def _patient_address(self):
        a = self.patient.address
        if not a:
            return None
        return (f"Logradouro: {a.street}, Nº: {a.number}, Bairro: {a.neighborhood}, "
                f"Cidade: {a.city}, Estado: {a.state}, CEP: {a.zip_code}")

    # ---------- clínica --------------------------------------------
    def _clinic_address(self):
        d = getattr(self.clinic, "data", None)
        if not d or not d.address:
            return None
        a = d.address
        return f"{a.street}, {a.number}, {a.neighborhood}, {a.city}/{a.state} - CEP {a.zip_code}"

    def _clinic_phone(self) -> str | None:
        # 1) usa pré-fetch, se veio
        phones = getattr(self.clinic, "prefetched_phones", None)
        if phones:
            return phones[0].phone_number

        # 2) fallback – consulta rápida
        return (
            ClinicPhone.objects
            .filter(clinic_id=self.clinic.id)
            .values_list("phone_number", flat=True)
            .first()
        )

    def _payment_method(self):
        return self.contract.payment_method.name if self.contract.payment_method else None
