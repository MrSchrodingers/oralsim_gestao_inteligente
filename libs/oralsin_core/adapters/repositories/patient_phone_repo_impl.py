from __future__ import annotations

from oralsin_core.adapters.utils.phone_utils import normalize_phone
from oralsin_core.core.application.cqrs import PagedResult
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
        
    def _sanitize_entity(self, entity: PatientPhoneEntity) -> PatientPhoneEntity:
        norm = normalize_phone(entity.phone_number, default_region="BR", digits_only=True, with_plus=False)
        if not norm:
            # você pode levantar uma DomainError/ValueError específica do projeto
            raise ValueError(f"Telefone inválido: {entity.phone_number!r}")
        entity.phone_number = norm
        return entity

    # ───────────────────────── CRUD ────────────────────────────
    def save(self, entity: PatientPhoneEntity) -> PatientPhoneEntity:
        entity = self._sanitize_entity(entity)
        data = {k: v for k, v in entity.to_dict().items() if k in self._allowed() and k != "id"}
        model, _ = PatientPhoneModel.objects.update_or_create(id=entity.id, defaults=data)
        return PatientPhoneEntity.from_model(model)

    def update(self, entity: PatientPhoneEntity) -> PatientPhoneEntity:
        entity = self._sanitize_entity(entity)
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

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[PatientPhoneEntity]:
        """
        Retorna PagedResult contendo lista de PatientPhoneEntity e total,
        aplicando paginação sobre PatientPhoneModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = PatientPhoneModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        pacientes_telefone_page = qs.order_by('id')[offset: offset + page_size]

        items = [PatientPhoneEntity.from_model(m) for m in pacientes_telefone_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)