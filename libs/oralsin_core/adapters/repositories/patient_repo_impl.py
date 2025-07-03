from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Q

from oralsin_core.core.application.cqrs import PagedResult
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
        
        data.pop("flow_type", None)
        
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
    def exists(self, oralsin_patient_id: int) -> bool:
        """Retorna True se o paciente já estiver no banco."""
        return PatientModel.objects.filter(
            oralsin_patient_id=oralsin_patient_id
        ).exists()

    @transaction.atomic
    def update(self, patient: PatientEntity) -> PatientEntity:
        """
        Atualiza **somente** campos mutáveis; nunca cria registro.
        Lança `PatientModel.DoesNotExist` se o paciente não existir.
        """
        model: PatientModel = PatientModel.objects.get(
            oralsin_patient_id=patient.oralsin_patient_id
        )

        # 1) endereço
        if patient.address:
            saved_addr = self._address_repo.save(
                patient.address
                if isinstance(patient.address, AddressEntity)
                else AddressEntity.from_dict(patient.address)
            )
            model.address_id = saved_addr.id

        # 2) campos simples
        # (ignora clinic_id, oralsin_patient_id, id)
        updatable = (
            "name",
            "cpf",
            "contact_name",
            "email",
            "is_notification_enabled",
        )
        changed = False
        for fld in updatable:
            new_val = getattr(patient, fld, None)
            if new_val is not None and getattr(model, fld) != new_val:
                setattr(model, fld, new_val)
                changed = True

        if changed:
            model.save(update_fields=[*updatable, "address_id"])

        return PatientEntity.from_model(model)
    
    def delete(self, patient_id: str) -> None:
        PatientModel.objects.filter(id=patient_id).delete()

    def list(self, filtros: dict, page: int, page_size: int, user_id = str) -> PagedResult[PatientEntity]:
        """
        Retorna PagedResult contendo lista de PatientEntity e total,
        aplicando paginação sobre PatientModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = PatientModel.objects.all()
        
        # 1) trata filtro especial de flow_type
        flow = filtros.pop("flow_type", None)
        search = filtros.pop("search", "").strip() 
        
        if flow == "notification_billing":
            # tem schedule mas não tem collectioncase
            qs = qs.filter(schedules__isnull=False).exclude(collectioncase__isnull=False)
        elif flow == "cordial_billing":
            # tem collectioncase (notification é irrelevante)
            qs = qs.filter(collectioncase__isnull=False)
        

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)
            
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(cpf__icontains=search)  |
                Q(email__icontains=search)
            )

        total = qs.count()
        offset = (page - 1) * page_size
        pacientes_page = qs.order_by('contact_name')[offset: offset + page_size]

        items = [PatientEntity.from_model(m) for m in pacientes_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)