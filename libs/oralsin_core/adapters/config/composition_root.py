from dependency_injector import containers, providers

container = None

def setup_di_container_from_settings(settings):  # noqa: PLR0915
    """Inicializa o DI container após o Django já estar com settings carregados."""
    global container  # noqa: PLW0603
    if container is not None:
        import structlog
        structlog.get_logger().debug("DI container já inicializado.")
        return container

    # ------- IMPORTS QUE USAM DJANGO MODELS -------
    import redis
    import structlog

    # API client, mappers e infra de mensageria...
    from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
    from oralsin_core.adapters.repositories.address_repo_impl import AddressRepoImpl
    from oralsin_core.adapters.repositories.clinic_data_repo_impl import ClinicDataRepoImpl
    from oralsin_core.adapters.repositories.clinic_phone_repo_impl import ClinicPhoneRepoImpl
    from oralsin_core.adapters.repositories.clinic_repo_impl import ClinicRepoImpl
    from oralsin_core.adapters.repositories.contract_repo_impl import ContractRepoImpl
    from oralsin_core.adapters.repositories.covered_clinic_repo_impl import CoveredClinicRepoImpl
    from oralsin_core.adapters.repositories.installment_repo_impl import InstallmentRepoImpl
    from oralsin_core.adapters.repositories.patient_phone_repo_impl import PatientPhoneRepoImpl
    from oralsin_core.adapters.repositories.patient_repo_impl import PatientRepoImpl
    from oralsin_core.adapters.repositories.user_clinic_repo_impl import UserClinicRepoImpl
    from oralsin_core.adapters.repositories.user_repo_impl import UserRepoImpl

    # Hash service para usuários
    from oralsin_core.adapters.security.hash_service import HashService

    # Commands
    from oralsin_core.core.application.commands.address_commands import CreateAddressCommand, DeleteAddressCommand, UpdateAddressCommand
    from oralsin_core.core.application.commands.clinic_commands import CreateClinicCommand, DeleteClinicCommand, UpdateClinicCommand
    from oralsin_core.core.application.commands.clinic_data_commands import CreateClinicDataCommand, UpdateClinicDataCommand
    from oralsin_core.core.application.commands.clinic_phone_commands import CreateClinicPhoneCommand, DeleteClinicPhoneCommand, UpdateClinicPhoneCommand
    from oralsin_core.core.application.commands.coverage_commands import LinkUserClinicCommand, RegisterCoverageClinicCommand
    from oralsin_core.core.application.commands.patient_phone_commands import CreatePatientPhoneCommand, DeletePatientPhoneCommand, UpdatePatientPhoneCommand
    from oralsin_core.core.application.commands.sync_commands import (
        SyncInadimplenciaCommand,
    )
    from oralsin_core.core.application.commands.user_commands import CreateUserCommand, DeleteUserCommand, UpdateUserCommand

    # CQRS buses
    from oralsin_core.core.application.cqrs import CommandBusImpl, QueryBusImpl

    # Handlers de CRUD
    from oralsin_core.core.application.handlers.core_entities_handlers import (
        CreateAddressHandler,
        CreateClinicDataHandler,
        CreateClinicHandler,
        CreateClinicPhoneHandler,
        CreatePatientPhoneHandler,
        CreateUserHandler,
        DeleteAddressHandler,
        DeleteClinicHandler,
        DeleteClinicPhoneHandler,
        DeletePatientPhoneHandler,
        DeleteUserHandler,
        LinkUserClinicHandler,
        UpdateAddressHandler,
        UpdateClinicDataHandler,
        UpdateClinicHandler,
        UpdateClinicPhoneHandler,
        UpdatePatientPhoneHandler,
        UpdateUserHandler,
    )
    from oralsin_core.core.application.handlers.coverage_handlers import RegisterCoverageClinicHandler
    from oralsin_core.core.application.handlers.dashboard_handlers import GetDashboardSummaryHandler

    # Implementações concretas de repositórios
    from oralsin_core.core.application.handlers.sync_handlers import SyncInadimplenciaHandler
    from oralsin_core.core.application.services.dashboard_service import DashboardService
    from oralsin_core.core.application.services.oralsin_sync_service import OralsinSyncService
    from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
    from oralsin_core.core.domain.services.formatter_service import FormatterService
    container = None
    class Container(containers.DeclarativeContainer):
        config = providers.Configuration()

        # Infra & integração
        logger           = providers.Singleton(structlog.get_logger)
        event_dispatcher = providers.Singleton('oralsin_core.core.domain.services.event_dispatcher.EventDispatcher')

        # CQRS
        command_bus = providers.Singleton(CommandBusImpl, dispatcher=event_dispatcher)
        query_bus   = providers.Singleton(QueryBusImpl)

        # Redis, RabbitMQ, API clients, mappers...
        redis_client        = providers.Singleton(redis.Redis,
                                                host=config.redis.host,
                                                port=config.redis.port,
                                                db=config.redis.db,
                                                password=config.redis.password)
        oralsin_client      = providers.Singleton(OralsinAPIClient)
        oralsin_mapper      = providers.Singleton(OralsinPayloadMapper)

        # Implementações de Repositórios
        address_repo        = providers.Singleton(AddressRepoImpl)
        clinic_repo         = providers.Singleton(ClinicRepoImpl)
        contract_repo       = providers.Singleton(ContractRepoImpl)
        clinic_data_repo    = providers.Singleton(
            ClinicDataRepoImpl, 
            address_repo=address_repo
        )
        clinic_phone_repo   = providers.Singleton(ClinicPhoneRepoImpl)
        covered_clinic_repo = providers.Singleton(CoveredClinicRepoImpl)
        patient_phone_repo  = providers.Singleton(PatientPhoneRepoImpl)
        patient_repo        = providers.Singleton(
            PatientRepoImpl,
            address_repo=address_repo,
        )
        installment_repo    = providers.Singleton(
            InstallmentRepoImpl,
            mapper=oralsin_mapper
        )
        user_repo           = providers.Singleton(UserRepoImpl)
        user_clinic_repo    = providers.Singleton(UserClinicRepoImpl)

        # Hash
        hash_service = providers.Singleton(HashService)

        # Handlers CRUD
        create_address_handler       = providers.Factory(CreateAddressHandler,        repo=address_repo)
        update_address_handler       = providers.Factory(UpdateAddressHandler,        repo=address_repo)
        delete_address_handler       = providers.Factory(DeleteAddressHandler,        repo=address_repo)

        create_clinic_handler        = providers.Factory(CreateClinicHandler,         repo=clinic_repo)
        update_clinic_handler        = providers.Factory(UpdateClinicHandler,         repo=clinic_repo)
        delete_clinic_handler        = providers.Factory(DeleteClinicHandler,         repo=clinic_repo)

        create_clinic_data_handler   = providers.Factory(CreateClinicDataHandler,    repo=clinic_data_repo)
        update_clinic_data_handler   = providers.Factory(UpdateClinicDataHandler,    repo=clinic_data_repo)

        create_clinic_phone_handler  = providers.Factory(CreateClinicPhoneHandler,   repo=clinic_phone_repo)
        update_clinic_phone_handler  = providers.Factory(UpdateClinicPhoneHandler,   repo=clinic_phone_repo)
        delete_clinic_phone_handler  = providers.Factory(DeleteClinicPhoneHandler,   repo=clinic_phone_repo)

        create_patient_phone_handler = providers.Factory(CreatePatientPhoneHandler,  repo=patient_phone_repo)
        update_patient_phone_handler = providers.Factory(UpdatePatientPhoneHandler,  repo=patient_phone_repo)
        delete_patient_phone_handler = providers.Factory(DeletePatientPhoneHandler,  repo=patient_phone_repo)

        create_user_handler          = providers.Factory(CreateUserHandler,           repo=user_repo, hash_service=hash_service)
        update_user_handler          = providers.Factory(UpdateUserHandler,           repo=user_repo, hash_service=hash_service)
        delete_user_handler          = providers.Factory(DeleteUserHandler,           repo=user_repo)

        register_coverage_clinic_handler = providers.Factory(
            RegisterCoverageClinicHandler,
            api_client=oralsin_client,
            clinic_repo=clinic_repo,
            clinic_data_repo=clinic_data_repo,
            clinic_phone_repo=clinic_phone_repo,
            address_repo=address_repo,
            covered_repo=covered_clinic_repo,
            mapper=oralsin_mapper,
            command_bus=command_bus,
            dispatcher=event_dispatcher,
        )
        link_user_clinic_handler        = providers.Factory(LinkUserClinicHandler,        repo=user_clinic_repo)

        # Serviços de negócio
        formatter_service    = providers.Singleton(FormatterService, currency_symbol="R$")
        oralsin_sync_service = providers.Singleton(
            OralsinSyncService,
            command_bus=command_bus,
            query_bus=query_bus,
        )
        dashboard_service    = providers.Singleton(
            DashboardService,
            user_clinic_repo=user_clinic_repo,
            contract_repo=contract_repo,             
            installment_repo=installment_repo,          
            patient_repo=patient_repo,
            formatter=formatter_service,
        )
        sync_inadimplencia_handler = providers.Factory(
            SyncInadimplenciaHandler,
            api_client=oralsin_client,
            clinic_repo=clinic_repo,
            patient_repo=patient_repo,
            phone_repo=patient_phone_repo,
            contract_repo=contract_repo,
            installment_repo=installment_repo,
            mapper=oralsin_mapper,
            dispatcher=event_dispatcher,
        )
        dashboard_handler    = providers.Singleton(
            GetDashboardSummaryHandler,
            user_clinic_repo=user_clinic_repo,
            contract_repo=contract_repo,            
            installment_repo=installment_repo,         
            patient_repo=patient_repo,
            formatter=formatter_service,
        )
        
        def init(self):
            # Bus
            bus = self.command_bus()
            # Address
            bus.register(CreateAddressCommand, self.create_address_handler())
            bus.register(UpdateAddressCommand, self.update_address_handler())
            bus.register(DeleteAddressCommand, self.delete_address_handler())
            # Clinic
            bus.register(CreateClinicCommand, self.create_clinic_handler())
            bus.register(UpdateClinicCommand, self.update_clinic_handler())
            bus.register(DeleteClinicCommand, self.delete_clinic_handler())
            # Clinic Data
            bus.register(CreateClinicDataCommand, self.create_clinic_data_handler())
            bus.register(UpdateClinicDataCommand, self.update_clinic_data_handler())
            # Clinic Phone
            bus.register(CreateClinicPhoneCommand, self.create_clinic_phone_handler())
            bus.register(UpdateClinicPhoneCommand, self.update_clinic_phone_handler())
            bus.register(DeleteClinicPhoneCommand, self.delete_clinic_phone_handler())
            # Patient Phone
            bus.register(CreatePatientPhoneCommand, self.create_patient_phone_handler())
            bus.register(UpdatePatientPhoneCommand, self.update_patient_phone_handler())
            bus.register(DeletePatientPhoneCommand, self.delete_patient_phone_handler())
            # User
            bus.register(CreateUserCommand, self.create_user_handler())
            bus.register(UpdateUserCommand, self.update_user_handler())
            bus.register(DeleteUserCommand, self.delete_user_handler())
            # Covered Clinic & User-Clinic
            bus.register(RegisterCoverageClinicCommand, self.register_coverage_clinic_handler())
            bus.register(LinkUserClinicCommand, self.link_user_clinic_handler())
            # Sync Inadimplência
            bus.register(SyncInadimplenciaCommand,    self.sync_inadimplencia_handler())
            
    # ------- INSTANCIAÇÃO E CONFIG -------
    container = Container()
    container.config.rabbitmq_url.from_value(settings.RABBITMQ_URL)
    container.config.redis.host.from_value(settings.REDIS_HOST)
    container.config.redis.port.from_value(settings.REDIS_PORT)
    container.config.redis.db.from_value(settings.REDIS_DB)
    container.config.redis.password.from_value(settings.REDIS_PASSWORD)
    Container.init(container)
    return container