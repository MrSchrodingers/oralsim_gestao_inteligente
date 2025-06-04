from oralsin_core.core.domain.entities.user_clinic_entity import UserClinicEntity
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
from plugins.django_interface.models import UserClinic as UserClinicModel


class UserClinicRepoImpl(UserClinicRepository):
    def find_by_user(self, user_id: str) -> list[UserClinicEntity]:
        qs = UserClinicModel.objects.filter(user_id=user_id)
        return [UserClinicEntity.from_model(m) for m in qs]

    def find_by_clinic(self, clinic_id: str) -> list[UserClinicEntity]:
        qs = UserClinicModel.objects.filter(clinic_id=clinic_id)
        return [UserClinicEntity.from_model(m) for m in qs]

    def save(self, link: UserClinicEntity) -> UserClinicEntity:
        m, _ = UserClinicModel.objects.update_or_create(
            user_id=link.user_id,
            clinic_id=link.clinic_id,
            defaults=link.to_dict()
        )
        return UserClinicEntity.from_model(m)

    def delete(self, user_id: str, clinic_id: str) -> None:
        UserClinicModel.objects.filter(user_id=user_id, clinic_id=clinic_id).delete()
