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
