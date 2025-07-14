"""
Composition-root do *cordial_billing*.

• Carregado apenas depois que Django já aplicou as `settings`.
• Devolve um singleton `container` com todos os providers + handlers
  registrados no `command_bus`.
"""
from dependency_injector import containers, providers

container = None  # type: ignore


# ────────────────────────────────────────────────────────────────────
def setup_di_container_from_settings(settings):                      # noqa: PLR0915
    """
    Lazy-factory do DI container.  Pode ser chamada quantas vezes
    for necessário – sempre retorna a mesma instância.
    """
    global container                                                 # noqa: PLW0603
    if container is not None:
        import structlog

        structlog.get_logger(__name__).debug(
            "CordialBilling DI container já instanciado."
        )
        return container

    import structlog
    from oralsin_core.adapters.config.composition_root import (
        setup_di_container_from_settings as _setup_core_di,
    )
    from sqlalchemy.ext.asyncio import create_async_engine

    core_container = _setup_core_di(settings)

    from oralsin_core.adapters.repositories.billing_settings_repo_impl import (
        BillingSettingsRepoImpl,
    )
    from oralsin_core.adapters.repositories.covered_clinic_repo_impl import (
        CoveredClinicRepoImpl,
    )

    from cordial_billing.adapters.api_clients.pipedrive_api_client import (
        PipedriveAPIClient,
    )
    from cordial_billing.adapters.repositories.activity_repo_impl import (
        ActivityRepoImpl,
    )
    from cordial_billing.adapters.repositories.collection_case_repo_impl import (
        CollectionCaseRepoImpl,
    )
    from cordial_billing.adapters.repositories.deal_repo_impl import (
        DealRepoImpl,
    )
    from cordial_billing.adapters.repositories.org_repo_impl import OrganizationRepoImpl
    from cordial_billing.core.application.commands.collect_commands import (
        SyncOldDebtsCommand,
    )
    from cordial_billing.core.application.commands.create_deal_command import (
        CreatePipedriveDealCommand,
    )
    from cordial_billing.core.application.commands.sync_acordo_activity_commands import (
        SyncAcordoActivitiesCommand,
    )
    from cordial_billing.core.application.commands.update_deal_command import UpdatePipedriveDealCommand
    from cordial_billing.core.application.handlers.collection_case_handler import (
        GetCollectionCaseHandler,
        ListCollectionCaseHandler,
    )
    from cordial_billing.core.application.handlers.create_deal_handler import (
        CreatePipedriveDealHandler,
    )
    from cordial_billing.core.application.handlers.sync_acordo_activity_handler import (
        SyncAcordoActivitiesHandler,
    )
    from cordial_billing.core.application.handlers.sync_debts_handler import (
        SyncOldDebtsHandler,
    )
    from cordial_billing.core.application.handlers.update_deal_handler import UpdatePipedriveDealHandler
    from cordial_billing.core.application.queries.collection_case_queries import (
        GetCollectionCaseQuery,
        ListCollectionCasesQuery,
    )
    from cordial_billing.core.application.services.pipedrive_sync_service import (
        PipedriveSyncService,
    )
    from cordial_billing.core.domain.services.event_dispatcher import (
        EventDispatcher,
    )
    from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ
    from notification_billing.core.application.cqrs import CommandBusImpl, QueryBusImpl
    # ─── CONTAINER ─────────────────────────────────────────────────
    class Container(containers.DeclarativeContainer):
        wiring_config = containers.WiringConfiguration(packages=[])

        # --- configuração -----------------------------------------
        config = providers.Configuration()

        # --- cross-cutting ----------------------------------------
        logger      = providers.Singleton(structlog.get_logger, __name__)
        dispatcher  = providers.Singleton(EventDispatcher)
        command_bus = providers.Singleton(CommandBusImpl, dispatcher=dispatcher)
        query_bus   = providers.Singleton(QueryBusImpl)

        # --- conexões externas ------------------------------------
        pipeboard_engine = providers.Singleton(
            create_async_engine,
            url=config.pipeboard.dsn,
            pool_size=5,
            max_overflow=2,
        )
        rabbit = providers.Singleton(
            RabbitMQ,
            url=config.rabbitmq_url,
        )
        pipedrive_client = providers.Singleton(PipedriveAPIClient)

        # --- repositórios -----------------------------------------
        deal_repo = providers.Singleton(DealRepoImpl, pipeboard_engine=pipeboard_engine)
        org_repo  = providers.Singleton(OrganizationRepoImpl, pipeboard_engine=pipeboard_engine)
        activity_repo        = providers.Singleton(ActivityRepoImpl, pipeboard_engine=pipeboard_engine)
        collection_case_repo = providers.Singleton(CollectionCaseRepoImpl)
        billing_settings_repo = providers.Singleton(BillingSettingsRepoImpl)
        covered_clinic_repo   = providers.Singleton(CoveredClinicRepoImpl)

        # --- serviços --------------------------------------------
        pipedrive_sync_service = providers.Singleton(
            PipedriveSyncService,
            client=pipedrive_client,
            org_repo=org_repo,
        )

        # --- handlers ---------------------------------------------
        sync_old_debts_handler = providers.Factory(
            SyncOldDebtsHandler,
            installment_repo=core_container.installment_repo,
            patient_repo=core_container.patient_repo,
            deal_repo=deal_repo,
            case_repo=collection_case_repo,
            contract_repo=core_container.contract_repo,
            billing_settings_repo=billing_settings_repo,
            covered_clinic_repo=covered_clinic_repo,
            dispatcher=dispatcher,
            logger=logger,
        )
        create_deal_handler = providers.Factory(
            CreatePipedriveDealHandler,
            sync_service=pipedrive_sync_service,
        )
        list_collection_case_handler = providers.Factory(ListCollectionCaseHandler)
        get_collection_case_handler  = providers.Factory(GetCollectionCaseHandler)
        sync_acordo_activities_handler = providers.Factory(
            SyncAcordoActivitiesHandler,
            activity_repo=activity_repo,
            patient_repo=core_container.patient_repo,
            contract_repo=collection_case_repo,
            deal_repo=deal_repo,
            rabbit=rabbit,
        )
        update_deal_handler = providers.Factory(
            UpdatePipedriveDealHandler,
            sync_service=pipedrive_sync_service,
            activity_repo=activity_repo,
        )

        # ----------------------------------------------------------
        def init(self) -> None:
            """Registra handlers em CommandBus / QueryBus – executa 1×."""
            bus = self.command_bus()
            bus.register(SyncOldDebtsCommand, self.sync_old_debts_handler())
            bus.register(SyncAcordoActivitiesCommand, self.sync_acordo_activities_handler())
            bus.register(CreatePipedriveDealCommand, self.create_deal_handler())
            bus.register(UpdatePipedriveDealCommand, self.update_deal_handler())

            qry = self.query_bus()
            qry.register(ListCollectionCasesQuery, self.list_collection_case_handler())
            qry.register(GetCollectionCaseQuery,  self.get_collection_case_handler())

    # ─── INSTANTIAÇÃO + CONFIG ─────────────────────────────────────
    container = Container()
    container.config.pipeboard.dsn.from_value(settings.PIPEBOARD_DSN)
    container.config.rabbitmq_url.from_value(settings.RABBITMQ_URL)

    # registra os handlers
    Container.init(container)                                             # type: ignore[attr-defined]
    return container
