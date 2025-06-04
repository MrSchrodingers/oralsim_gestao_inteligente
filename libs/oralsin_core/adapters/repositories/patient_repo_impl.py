from __future__ import annotations

from django.db import IntegrityError

from oralsin_core.core.domain.entities.address_entity import AddressEntity
from oralsin_core.core.domain.entities.patient_entity import PatientEntity
from oralsin_core.core.domain.entities.patient_phone_entity import PatientPhoneEntity
from oralsin_core.core.domain.repositories.address_repository import AddressRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository
from plugins.django_interface.models import Patient as PatientModel
from plugins.django_interface.models import PatientPhone as PatientPhoneModel


class PatientRepoImpl(PatientRepository):
    """Repositório Django ORM – Pacientes."""

    def __init__(self, address_repo: AddressRepository) -> None:
        self._address_repo = address_repo

    # ───────────────────────── consultas ─────────────────────────
    def find_by_id(self, patient_id: str) -> PatientEntity | None:
        m = PatientModel.objects.filter(id=patient_id).first()
        if not m:
            return None
        phones = list(PatientPhoneModel.objects.filter(patient_id=patient_id))
        phones_entities = [PatientPhoneEntity.from_model(p) for p in phones]
        entity = PatientEntity.from_model(m)
        entity.phones = phones_entities
        return entity

    def find_by_oralsin_id(self, oralsin_patient_id: int) -> PatientEntity | None:
        try:
            return PatientEntity.from_model(
                PatientModel.objects.get(oralsin_patient_id=oralsin_patient_id)
            )
        except PatientModel.DoesNotExist:
            return None

    def find_by_clinic(self, clinic_id: str) -> list[PatientEntity]:
        return [
            PatientEntity.from_model(m)
            for m in PatientModel.objects.filter(clinic_id=clinic_id)
        ]

    # ───────────────────────── persistência ────────────────────────
    def save(self, patient: PatientEntity) -> PatientEntity:
        data = patient.to_dict()

        # 1) trata endereço
        addr = data.pop("address", None)
        if addr:
            addr_ent = addr if isinstance(addr, AddressEntity) else AddressEntity.from_dict(addr)
            saved_addr = self._address_repo.save(addr_ent)
            data["address_id"] = saved_addr.id

        # 2) força FK da clínica
        data["clinic_id"] = patient.clinic_id

        # 3) nunca incluir o id interno no defaults
        data.pop("id", None)

        # 4) lookup por oralsin_patient_id
        lookup = {"oralsin_patient_id": patient.oralsin_patient_id}

        try:
            model, created = PatientModel.objects.update_or_create(
                defaults=data,
                **lookup
            )
        except IntegrityError as e:
            if "patients_address_id_key" in str(e):
                # neste caso a gente só atualiza o paciente que já “tem” esse endereço
                model = PatientModel.objects.get(address_id=data["address_id"])
                # e, opcionalmente, atualiza outros campos
                for k, v in data.items():
                    setattr(model, k, v)
                model.save(update_fields=list(data.keys()))
                _created = False
            else:
                raise

        return PatientEntity.from_model(model)

    # -----------------------------------------------------------------
    def delete(self, patient_id: str) -> None:
        PatientModel.objects.filter(id=patient_id).delete()
