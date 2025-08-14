from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.user_entity import UserEntity
from oralsin_core.core.domain.repositories.user_repository import UserRepository
from plugins.django_interface.models import User as UserModel


class UserRepoImpl(UserRepository):
    def find_by_id(self, user_id: str) -> UserEntity | None:
        try:
            m = UserModel.objects.get(id=user_id)
            return UserEntity.from_model(m)
        except UserModel.DoesNotExist:
            return None

    def find_by_email(self, email: str) -> UserEntity | None:
        try:
            m = UserModel.objects.get(email=email)
            return UserEntity.from_model(m)
        except UserModel.DoesNotExist:
            return None

    def find_by_role(self, role: str) -> list[UserEntity]:
        qs = UserModel.objects.filter(role=role)
        return [UserEntity.from_model(m) for m in qs]

    def find_all(self) -> list[UserEntity]:
        return [UserEntity.from_model(m) for m in UserModel.objects.all()]

    def save(self, entity: UserEntity) -> UserEntity:
        m, _ = UserModel.objects.update_or_create(
            id=entity.id,
            defaults=entity.to_dict()
        )
        return UserEntity.from_model(m)

    def update(self, entity: UserEntity) -> UserEntity:
        model = UserModel.objects.get(id=entity.id)
        for k, v in entity.to_dict().items():
            setattr(model, k, v)
        model.save(update_fields=(entity.to_dict().keys()))
        return UserEntity.from_model(model)

    def delete(self, user_id: str) -> None:
        UserModel.objects.filter(id=user_id).delete()
        
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[UserEntity]:
        """
        Retorna PagedResult contendo lista de UserEntity e total,
        aplicando paginação sobre UserModel.

        - filtros: dicionário de filtros (ex.: {'role': 'admin', 'email__icontains': 'foo'})
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = UserModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        usuarios_page = qs.order_by('id')[offset: offset + page_size]

        items = [UserEntity.from_model(m) for m in usuarios_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)
