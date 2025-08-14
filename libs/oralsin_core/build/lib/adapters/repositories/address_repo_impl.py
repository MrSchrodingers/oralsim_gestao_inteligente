from django.db.models import Q

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.address_entity import AddressEntity
from oralsin_core.core.domain.repositories.address_repository import AddressRepository
from plugins.django_interface.models import Address as AddressModel


class AddressRepoImpl(AddressRepository):
    def find_by_id(self, address_id: str) -> AddressEntity | None:
        try:
            m = AddressModel.objects.get(id=address_id)
            return AddressEntity.from_model(m)
        except AddressModel.DoesNotExist:
            return None

    def find_all(self) -> list[AddressEntity]:
        return [AddressEntity.from_model(m) for m in AddressModel.objects.all()]

    def save(self, address: AddressEntity) -> AddressEntity:
        # normalize your key fields
        street   = address.street.strip()
        number   = address.number.strip()
        zip_code = (address.zip_code or "").strip()

        # build defaults for the other columns
        defaults = {
            "complement":   address.complement,
            "neighborhood": address.neighborhood,
            "city":         address.city,
            "state":        address.state,
        }

        m, created = AddressModel.objects.update_or_create(
            street=street,
            number=number,
            zip_code=zip_code,
            defaults=defaults,
        )

        return AddressEntity.from_model(m)

    def delete(self, address_id: str) -> None:
        AddressModel.objects.filter(id=address_id).delete()

    def list(
        self, filtros: dict, page: int, page_size: int
    ) -> PagedResult[AddressEntity]:

        qs = AddressModel.objects.all()

        clinic_id = filtros.pop("clinic_id", None)

        # ── 1️⃣  Aplica filtros simples que vieram na query-string
        if filtros:
            qs = qs.filter(**filtros)

        # ── 2️⃣  Se veio clinic_id, restringe por:
        #         (A) pacientes da clínica  OR  (B) address da própria clínica
        if clinic_id:
            qs = qs.filter(
                Q(patient__clinic_id=clinic_id) |
                Q(clinics__clinic_id=clinic_id)   # via ClinicData
            )

        qs = qs.distinct()        # evita duplicatas quando cair nos dois casos

        # ── 3️⃣  Paginação padrão
        total   = qs.count()
        offset  = (page - 1) * page_size
        page_qs = qs.order_by("id")[offset : offset + page_size]

        items = [AddressEntity.from_model(m) for m in page_qs]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)