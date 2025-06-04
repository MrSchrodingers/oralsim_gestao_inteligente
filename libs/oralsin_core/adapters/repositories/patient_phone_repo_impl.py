from __future__ import annotations

from oralsin_core.core.domain.entities.patient_phone_entity import PatientPhoneEntity
from oralsin_core.core.domain.repositories.patient_phone_repository import (
    PatientPhoneRepository,
)
from plugins.django_interface.models import PatientPhone as PatientPhoneModel


class PatientPhoneRepoImpl(PatientPhoneRepository):
    # ───────────────────────── helpers ─────────────────────────
    @staticmethod
    def _allowed() -> set[str]:
        """Campos realmente presentes na tabela – evita FieldError."""
        return {
            f.name
            for f in PatientPhoneModel._meta.get_fields()
            if not f.is_relation or f.many_to_one
        }

    # ───────────────────────── CRUD ────────────────────────────
    def save(self, entity: PatientPhoneEntity) -> PatientPhoneEntity:  # noqa: D401
        data = {k: v for k, v in entity.to_dict().items() if k in self._allowed() and k != "id"}
        model, _ = PatientPhoneModel.objects.update_or_create(id=entity.id, defaults=data)
        return PatientPhoneEntity.from_model(model)

    def update(self, entity: PatientPhoneEntity) -> PatientPhoneEntity:
        data = {k: v for k, v in entity.to_dict().items() if k in self._allowed() and k != "id"}
        PatientPhoneModel.objects.filter(id=entity.id).update(**data)
        model = PatientPhoneModel.objects.get(id=entity.id)
        return PatientPhoneEntity.from_model(model)

    def delete(self, phone_id: str) -> None:
        PatientPhoneModel.objects.filter(id=phone_id).delete()

    # ────────────── consultas simples ──────────────
    def find_by_id(self, phone_id: str) -> PatientPhoneEntity | None:
        try:
            return PatientPhoneEntity.from_model(PatientPhoneModel.objects.get(id=phone_id))
        except PatientPhoneModel.DoesNotExist:
            return None

    def find_all(self) -> list[PatientPhoneEntity]:
        return [PatientPhoneEntity.from_model(m) for m in PatientPhoneModel.objects.all()]

    def find_by_patient(self, patient_id: str) -> list[PatientPhoneEntity]:
        return [
            PatientPhoneEntity.from_model(m)
            for m in PatientPhoneModel.objects.filter(patient_id=patient_id)
        ]
