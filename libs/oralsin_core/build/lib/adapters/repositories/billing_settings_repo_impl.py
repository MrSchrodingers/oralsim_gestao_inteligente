from oralsin_core.core.application.cqrs import PagedResult
from oralsin_core.core.domain.entities.billing_settings_entity import BillingSettingsEntity
from oralsin_core.core.domain.repositories.billing_settings_repository import BillingSettingsRepository
from plugins.django_interface.models import BillingSettings as BillingSettingsModel


class BillingSettingsRepoImpl(BillingSettingsRepository):
    def get(self, clinic_id: str) -> BillingSettingsEntity | None:
        try:
            m = BillingSettingsModel.objects.get(clinic_id=clinic_id)
            return BillingSettingsEntity(clinic_id=m.clinic_id, min_days_overdue=m.min_days_overdue)
        except BillingSettingsModel.DoesNotExist:
            return None

    def update(self, settings: BillingSettingsEntity) -> BillingSettingsEntity:
        m, _ = BillingSettingsModel.objects.update_or_create(
            clinic_id=settings.clinic_id,
            defaults={"min_days_overdue": settings.min_days_overdue},
        )
        return BillingSettingsEntity(
            clinic_id=m.clinic_id,
            min_days_overdue=m.min_days_overdue,
        )
    
    
    def list(self, filtros: dict, page: int, page_size: int) -> PagedResult[BillingSettingsEntity]:
        """
        Retorna PagedResult contendo lista de ClinicDataEntity e total,
        aplicando paginação sobre ClinicDataModel.

        - filtros: dicionário de filtros 
        - page: número da página (1-based)
        - page_size: quantidade de itens por página
        """
        qs = BillingSettingsModel.objects.all()

        # Aplica filtros simples se houver campos em `filtros`
        if filtros:
            qs = qs.filter(**filtros)

        total = qs.count()
        offset = (page - 1) * page_size
        clinica_data_page = qs.order_by('id')[offset: offset + page_size]

        items = [BillingSettingsEntity.from_model(m) for m in clinica_data_page]
        return PagedResult(items=items, total=total, page=page, page_size=page_size)