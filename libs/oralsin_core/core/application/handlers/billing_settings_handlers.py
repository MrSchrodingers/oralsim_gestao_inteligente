from oralsin_core.core.application.cqrs import CommandHandler, PagedResult, QueryHandler
from oralsin_core.core.domain.entities.billing_settings_entity import BillingSettingsEntity
from oralsin_core.core.domain.repositories.billing_settings_repository import BillingSettingsRepository

from ..commands.billing_settings_commands import UpdateBillingSettingsCommand
from ..queries.billing_settings_queries import GetBillingSettingsQuery, ListBillingSettingsQuery


class GetBillingSettingsHandler(QueryHandler[GetBillingSettingsQuery, BillingSettingsEntity | None]):
    def __init__(self, repo: BillingSettingsRepository):
        self.repo = repo

    def handle(self, q: GetBillingSettingsQuery) -> BillingSettingsEntity | None:
        return self.repo.get(q.filtros.get("clinic_id"))

class UpdateBillingSettingsHandler(CommandHandler[UpdateBillingSettingsCommand]):
    def __init__(self, repo: BillingSettingsRepository):
        self.repo = repo

    def handle(self, cmd: UpdateBillingSettingsCommand) -> BillingSettingsEntity:
        entity = BillingSettingsEntity(clinic_id=cmd.clinic_id, min_days_overdue=cmd.min_days_overdue)
        return self.repo.update(entity)


class ListBillingSettingsHandler(QueryHandler[ListBillingSettingsQuery, PagedResult[BillingSettingsEntity]]):
    def __init__(self, repo: BillingSettingsRepository):
        self.repo = repo

    def handle(self, q: ListBillingSettingsQuery) -> PagedResult[BillingSettingsEntity]:
        """
        Retorna configurações de cobrança paginadas.
        """
        return self.repo.list(
            filtros=q.filtros,
            page=q.page,
            page_size=q.page_size,
        )