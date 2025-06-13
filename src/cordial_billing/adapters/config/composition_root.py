"""
Composition-root do *cordial_billing*.

• Carregado apenas depois que Django já aplicou as `settings`.
• Devolve um singleton `container` com todos os providers + handlers
  registrados no `command_bus`.
"""
from dependency_injector import containers, providers

from cordial_billing.core.application.handlers.collection_case_handler import GetCollectionCaseHandler, ListCollectionCaseHandler
from cordial_billing.core.application.queries.collection_case_queries import GetCollectionCaseQuery, ListCollectionCasesQuery
from notification_billing.core.application.cqrs import QueryBusImpl

container = None  # type: ignore


# ────────────────────────────────────────────────────────────────────
def setup_di_container_from_settings(settings):         # noqa: PLR0915
    """
    Lazy-factory do DI container.  Pode ser chamada quantas vezes
    for necessário – sempre retorna a mesma instância.
    """
    global container  # noqa: PLW0603
    if container is not None:
        import structlog

        structlog.get_logger(__name__).debug(
            "CordialBilling DI container já instanciado."
        )
        return container

    # ─── IMPORTS (deferred para depois do Django) ───────────────────
    import structlog

    # ------------- dependências de outros bounded-contexts ----------
    from oralsin_core.adapters.config.composition_root import (
        setup_di_container_from_settings as _setup_core_di,
    )
    from sqlalchemy.ext.asyncio import create_async_engine

    core_container = _setup_core_di(settings)

    # ------------- repositórios desta BC ---------------------------
    from oralsin_core.adapters.repositories.billing_settings_repo_impl import BillingSettingsRepoImpl
    from oralsin_core.adapters.repositories.covered_clinic_repo_impl import CoveredClinicRepoImpl

    from cordial_billing.adapters.repositories.collection_case_repo_impl import (
        CollectionCaseRepoImpl,
    )
    from cordial_billing.adapters.repositories.deal_repo_impl import (
        DealRepoImpl,
    )

    # ------------- comandos / handlers -----------------------------
    from cordial_billing.core.application.commands.collect_commands import (
        SyncOldDebtsCommand,
    )
    from cordial_billing.core.application.handlers.sync_debts_handler import (
        SyncOldDebtsHandler,
    )

    # ------------- infra CQRS / domínio ----------------------------
    from cordial_billing.core.domain.services.event_dispatcher import (
        EventDispatcher,
    )
    from notification_billing.core.application.cqrs import CommandBusImpl

    # ─── CONTAINER DEFINIÇÃO ───────────────────────────────────────
    class Container(containers.DeclarativeContainer):
        wiring_config = containers.WiringConfiguration(packages=[])

        # --- configuração -----------------------------------------
        config = providers.Configuration()

        # --- cross-cutting ----------------------------------------
        logger = providers.Singleton(structlog.get_logger, __name__)
        dispatcher = providers.Singleton(EventDispatcher)
        command_bus = providers.Singleton(CommandBusImpl, dispatcher=dispatcher)
        query_bus   = providers.Singleton(QueryBusImpl)
        
        # --- conexões externas ------------------------------------
        pipeboard_engine = providers.Singleton(
            create_async_engine,
            url=config.pipeboard.dsn,
            pool_size=5,
            max_overflow=2,
        )

        # --- repositórios -----------------------------------------
        deal_repo = providers.Singleton(
            DealRepoImpl,
            pipeboard_engine=pipeboard_engine,
        )
        collection_case_repo = providers.Singleton(CollectionCaseRepoImpl)
        billing_settings_repo = providers.Singleton(BillingSettingsRepoImpl)
        covered_clinic_repo = providers.Singleton(CoveredClinicRepoImpl)
        # --- handlers ---------------------------------------------
        sync_old_debts_handler = providers.Factory(
            SyncOldDebtsHandler,
            installment_repo=core_container.installment_repo,
            patient_repo=core_container.patient_repo,
            deal_repo=deal_repo,
            case_repo=collection_case_repo,
            contract_repo=core_container.contract_repo,
            billing_settings_repo=billing_settings_repo,
            covered_clinic_repo = covered_clinic_repo,
            dispatcher=dispatcher,
            logger=logger,
        )

        
        list_collection_case_handler    = providers.Factory(ListCollectionCaseHandler)
        get_collection_case_handler     = providers.Factory(GetCollectionCaseHandler)
        
        # ----------------------------------------------------------
        def init(self) -> None:
            """Registra handlers no CommandBus (executado 1×)."""
            bus = self.command_bus()
            bus.register(SyncOldDebtsCommand, self.sync_old_debts_handler())
            
            qry_bus = self.query_bus()
            qry_bus.register(ListCollectionCasesQuery, self.list_collection_case_handler()) 
            qry_bus.register(GetCollectionCaseQuery, self.get_collection_case_handler())

    # ─── INSTANTIAÇÃO + CONFIGURAÇÃO ───────────────────────────────
    container = Container()
    container.config.pipeboard.dsn.from_value(settings.PIPEBOARD_DSN)

    # registra handlers
    Container.init(container)  # type: ignore[attr-defined]
    return container
