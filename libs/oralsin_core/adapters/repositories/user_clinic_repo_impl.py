from django.db import transaction

from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.user_clinic_entity import UserClinicEntity
from oralsin_core.core.domain.entities.user_entity import UserEntity
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
from plugins.django_interface.models import Clinic as ClinicModel
from plugins.django_interface.models import User as UserModel
from plugins.django_interface.models import UserClinic as UserClinicModel


class UserClinicRepoImpl(UserClinicRepository):
    
    def create_user_with_clinic(*, email: str, password_hash: str,
                            name: str, clinic_id: str, **extra) -> UserEntity:
        """
        Cria User + vínculo UserClinic em uma tacada só.
        Levanta IntegrityError se já existir.
        """
        with transaction.atomic():
            user = UserModel.objects.create(
                email=email.lower(),
                password_hash=password_hash,
                name=name,
                role=UserModel.Role.CLINIC,
                **extra,
            )
            UserClinicModel.objects.create(
                user=user,
                clinic=ClinicModel.objects.get(id=clinic_id),
            )
        return user

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

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[UserClinicEntity]:
        """
        Retorna PagedResult contendo lista de UserClinicEntity e total,
        aplicando paginação sobre UserClinicModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = UserClinicModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        usuarios_clinica_page = qs.order_by('id')[offset: offset + page_size]

        items = [UserClinicEntity.from_model(m) for m in usuarios_clinica_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)