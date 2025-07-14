from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.address_entity import AddressEntity
from oralsin_core.core.domain.entities.patient_entity import PatientEntity
from oralsin_core.core.domain.entities.patient_phone_entity import PatientPhoneEntity
from oralsin_core.core.domain.repositories.address_repository import AddressRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from plugins.django_interface.models import (
    Patient as PatientModel,
)
from plugins.django_interface.models import (
    PatientPhone as PatientPhoneModel,
)


class PatientRepoImpl(PatientRepository):
    """
    Implementação Django do repositório de pacientes.

    Estratégia de salvamento idempotente:
      • lookup primário  → oralsin_patient_id
      • fallback CPF     → cpf (casos legados sem ID externo)
      • se ambos ausentes→ cria novo registro (UUID aleatório)
      • NUNCA usa address_id como chave de deduplicação
    """

    def __init__(self, address_repo: AddressRepository) -> None:
        self._address_repo = address_repo

    # ────────────────────────── consultas ──────────────────────────
    def find_by_id(self, patient_id: str) -> PatientEntity | None:
        model = PatientModel.objects.filter(id=patient_id).first()
        if not model:
            return None

        phones = PatientPhoneModel.objects.filter(patient_id=patient_id)
        entity = PatientEntity.from_model(model)
        entity.phones = [PatientPhoneEntity.from_model(p) for p in phones]
        return entity

    def find_by_oralsin_id(self, oralsin_patient_id: int) -> PatientEntity | None:
        model = PatientModel.objects.filter(oralsin_patient_id=oralsin_patient_id).first()
        return PatientEntity.from_model(model) if model else None

    def find_by_clinic(self, clinic_id: str) -> list[PatientEntity]:
        return [
            PatientEntity.from_model(m)
            for m in PatientModel.objects.filter(clinic_id=clinic_id)
        ]

    # ─────────────────────── persistência (save) ───────────────────────
    @transaction.atomic
    def save(self, patient: PatientEntity) -> PatientEntity:
        # 1) endereço
        address_id: uuid.UUID | None = None
        if patient.address:
            addr_ent = (
                patient.address
                if isinstance(patient.address, AddressEntity)
                else AddressEntity.from_dict(patient.address)  # type: ignore[arg-type]
            )
            saved_addr = self._address_repo.save(addr_ent)
            address_id = saved_addr.id

        # 2) montagem do lookup
        lookup: dict[str, Any] = {"clinic_id": patient.clinic_id}
        if patient.oralsin_patient_id:
            lookup["oralsin_patient_id"] = patient.oralsin_patient_id
        elif patient.cpf:
            lookup["cpf"] = patient.cpf
        else:
            # Sem nenhum identificador confiável – força criação de novo UUID
            lookup["id"] = uuid.uuid4()

        # 3) campos mutáveis / defaults
        defaults = {
            "name": patient.name,
            "contact_name": patient.contact_name,
            "cpf": patient.cpf,
            "email": patient.email,
            "address_id": address_id,
            "updated_at": timezone.now(),
        }

        model, _ = PatientModel.objects.update_or_create(defaults=defaults, **lookup)
        return PatientEntity.from_model(model)

    # ------------------------------------------------------------------
    def exists(self, oralsin_patient_id: int) -> bool:
        return PatientModel.objects.filter(oralsin_patient_id=oralsin_patient_id).exists()

    # ─────────────────────────── update ────────────────────────────
    @transaction.atomic
    def update(self, patient: PatientEntity) -> PatientEntity:
        """
        Atualiza campos mutáveis de um paciente existente.
        Nunca cria registro novo.
        """
        model = PatientModel.objects.get(oralsin_patient_id=patient.oralsin_patient_id)

        # 1) endereço
        if patient.address:
            saved_addr = self._address_repo.save(
                patient.address
                if isinstance(patient.address, AddressEntity)
                else AddressEntity.from_dict(patient.address)  # type: ignore[arg-type]
            )
            model.address_id = saved_addr.id

        # 2) campos simples
        updatable = ("name", "cpf", "contact_name", "email")
        changed = False
        for field in updatable:
            new_val = getattr(patient, field, None)
            if new_val is not None and getattr(model, field) != new_val:
                setattr(model, field, new_val)
                changed = True

        if changed:
            model.updated_at = timezone.now()
            model.save(update_fields=[*updatable, "address_id", "updated_at"])

        return PatientEntity.from_model(model)

    # ------------------------------------------------------------------
    def delete(self, patient_id: str) -> None:
        PatientModel.objects.filter(id=patient_id).delete()

    # ─────────────────────── list (paginação) ────────────────────────
    def list(
        self,
        filtros: dict,
        page: int,
        page_size: int,
        user_id: str | None = None,
    ) -> PagedResult[PatientEntity]:
        """
        Retorna pacientes paginados com filtros opcionais.
        """
        qs = PatientModel.objects.all()

        # 1) filtro por flow_type
        flow = filtros.pop("flow_type", None)
        if flow == "notification_billing":
            qs = qs.filter(schedules__isnull=False).exclude(collectioncase__isnull=False)
        elif flow == "cordial_billing":
            qs = qs.filter(collectioncase__isnull=False)

        # 2) filtros simples diretos
        search = filtros.pop("search", "").strip()
        if filtros:
            qs = qs.filter(**filtros)

        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(cpf__icontains=search)
                | Q(email__icontains=search)
            )

        total = qs.count()
        offset = (page - 1) * page_size
        page_qs = qs.order_by("contact_name")[offset : offset + page_size]

        items = [PatientEntity.from_model(m) for m in page_qs]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
