import uuid

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.registration_request_entity import RegistrationRequestEntity
from oralsin_core.core.domain.repositories.registration_request_repository import RegistrationRequestRepository
from plugins.django_interface.models import RegistrationRequest as RegistrationRequestModel


class RegistrationRequestRepoImpl(RegistrationRequestRepository):
    def find_by_id(self, request_id: uuid.UUID) -> RegistrationRequestEntity | None:
        try:
            model = RegistrationRequestModel.objects.get(id=request_id)
            return RegistrationRequestEntity.from_model(model)
        except RegistrationRequestModel.DoesNotExist:
            return None

    def save(self, request: RegistrationRequestEntity) -> RegistrationRequestEntity:
        model, _ = RegistrationRequestModel.objects.update_or_create(
            id=request.id,
            defaults=request.to_dict()
        )
        return RegistrationRequestEntity.from_model(model)

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[RegistrationRequestEntity]:
        qs = RegistrationRequestModel.objects.filter(**filtros)
        total = qs.count()
        offset = (page - 1) * page_size
        paginated_qs = qs.order_by("-created_at")[offset: offset + page_size]
        items = [RegistrationRequestEntity.from_model(m) for m in paginated_qs]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)