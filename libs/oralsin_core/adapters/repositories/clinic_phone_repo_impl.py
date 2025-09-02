from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.clinic_phone_entity import ClinicPhoneEntity
from oralsin_core.core.domain.repositories.clinic_phone_repository import ClinicPhoneRepository
from plugins.django_interface.models import ClinicPhone as ClinicPhoneModel


class ClinicPhoneRepoImpl(ClinicPhoneRepository):
    def find_by_id(self, phone_id: str) -> ClinicPhoneEntity | None:
        try:
            m = ClinicPhoneModel.objects.get(id=phone_id)
            return ClinicPhoneEntity.from_model(m)
        except ClinicPhoneModel.DoesNotExist:
            return None

    def find_contact_by_clinic_id(self, clinic_id: str) -> ClinicPhoneEntity | None:
        try:
            m = ClinicPhoneModel.objects.get(clinic_id=clinic_id, phone_type="contact")
            return ClinicPhoneEntity.from_model(m)
        except ClinicPhoneModel.DoesNotExist:
            return None
        
    def _by_clinic(self, clinic_id: str) -> list[ClinicPhoneEntity]:
        qs = ClinicPhoneModel.objects.filter(clinic_id=clinic_id)
        return [ClinicPhoneEntity.from_model(m) for m in qs]

    def list_by_clinic(self, clinic_id: str) -> list[ClinicPhoneEntity]:
        return self._by_clinic(clinic_id)
    
    def save(self, phone: ClinicPhoneEntity) -> ClinicPhoneEntity:
        defaults = {
            "clinic_id": phone.clinic_id,
            "phone_number": phone.phone_number,
            "phone_type": phone.phone_type,
        }
        m, _ = ClinicPhoneModel.objects.update_or_create(
            id=phone.id,
            defaults=defaults,
        )
        return ClinicPhoneEntity.from_model(m)
    
    def save_contact_phone(self, phone: ClinicPhoneEntity, contact_phone: str) -> ClinicPhoneEntity:
        m, _ = ClinicPhoneModel.objects.update_or_create(
            clinic_id=phone.clinic_id,
            phone_type="contact",
            defaults={"phone_number": contact_phone},
        )
        return ClinicPhoneEntity.from_model(m)

    def delete(self, phone_id: str) -> None:
        ClinicPhoneModel.objects.filter(id=phone_id).delete()

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[ClinicPhoneEntity]:
        """
        Retorna PagedResult contendo lista de ClinicPhoneEntity e total,
        aplicando paginação sobre ClinicPhoneModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = ClinicPhoneModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        clinica_telefones_page = qs.order_by('id')[offset: offset + page_size]

        items = [ClinicPhoneEntity.from_model(m) for m in clinica_telefones_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)