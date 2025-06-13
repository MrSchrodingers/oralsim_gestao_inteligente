from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.payment_method_entity import PaymentMethodEntity
from oralsin_core.core.domain.repositories.payment_method_repository import PaymentMethodRepository
from plugins.django_interface.models import PaymentMethod as PaymentMethodModel


class PaymentMethodRepoImpl(PaymentMethodRepository):
    def find_by_id(self, payment_method_id: str) -> PaymentMethodEntity | None:
        try:
            m = PaymentMethodModel.objects.get(id=payment_method_id)
            return PaymentMethodEntity.from_model(m)
        except PaymentMethodModel.DoesNotExist:
            return None

    def find_by_oralsin_method_id(self, oralsin_method_id: str) -> PaymentMethodEntity | None:
        try:
            m = PaymentMethodModel.objects.get(oralsin_method_id=oralsin_method_id)
            return PaymentMethodEntity.from_model(m)
        except PaymentMethodModel.DoesNotExist:
            return None

    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[PaymentMethodEntity]:
            """
            Retorna PagedResult contendo lista de UserClinicEntity e total,
            aplicando paginação sobre UserClinicModel.

            - filtros: dicionário de filtros 
            - page: número da página (1-based)
            - page_size: quantidade de itens por página
            """
            qs = PaymentMethodModel.objects.all()

            # Aplica filtros simples se houver campos em `filtros`
            if filtros:
                qs = qs.filter(**filtros)

            total = qs.count()
            offset = (page - 1) * page_size
            usuarios_clinica_page = qs.order_by('id')[offset: offset + page_size]

            items = [PaymentMethodEntity.from_model(m) for m in usuarios_clinica_page]
            return PagedResult(items=items, total=total, page=page, page_size=page_size)