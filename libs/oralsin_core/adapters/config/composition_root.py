from dependency_injector import containers, providers

from cordial_billing.adapters.repositories.collection_case_repo_impl import CollectionCaseRepoImpl
from notification_billing.adapters.repositories.contact_history_repo_impl import ContactHistoryRepoImpl
from notification_billing.adapters.repositories.contact_schedule_repo_impl import ContactScheduleRepoImpl

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
    from oralsin_core.adapters.repositories.billing_settings_repo_impl import BillingSettingsRepoImpl
    from oralsin_core.adapters.repositories.clinic_data_repo_impl import ClinicDataRepoImpl
    from oralsin_core.adapters.repositories.clinic_phone_repo_impl import ClinicPhoneRepoImpl
    from oralsin_core.adapters.repositories.clinic_repo_impl import ClinicRepoImpl
    from oralsin_core.adapters.repositories.contract_repo_impl import ContractRepoImpl
    from oralsin_core.adapters.repositories.covered_clinic_repo_impl import CoveredClinicRepoImpl
    from oralsin_core.adapters.repositories.installment_repo_impl import InstallmentRepoImpl
    from oralsin_core.adapters.repositories.patient_phone_repo_impl import PatientPhoneRepoImpl
    from oralsin_core.adapters.repositories.patient_repo_impl import PatientRepoImpl
    from oralsin_core.adapters.repositories.payment_method_repo_impl import PaymentMethodRepoImpl
    from oralsin_core.adapters.repositories.user_clinic_repo_impl import UserClinicRepoImpl
    from oralsin_core.adapters.repositories.user_repo_impl import UserRepoImpl

    # Hash service para usuários
    from oralsin_core.adapters.security.hash_service import HashService

    # Commands
    from oralsin_core.core.application.commands.address_commands import (
        CreateAddressCommand,
        DeleteAddressCommand,
        UpdateAddressCommand,
    )
    from oralsin_core.core.application.commands.billing_settings_commands import UpdateBillingSettingsCommand
    from oralsin_core.core.application.commands.clinic_commands import (
        CreateClinicCommand,
        DeleteClinicCommand,
        UpdateClinicCommand,
    )
    from oralsin_core.core.application.commands.clinic_data_commands import (
        CreateClinicDataCommand,
        UpdateClinicDataCommand,
    )
    from oralsin_core.core.application.commands.clinic_phone_commands import (
        CreateClinicPhoneCommand,
        DeleteClinicPhoneCommand,
        UpdateClinicPhoneCommand,
    )
    from oralsin_core.core.application.commands.coverage_commands import (
        LinkUserClinicCommand,
        RegisterCoverageClinicCommand,
    )
    from oralsin_core.core.application.commands.patient_phone_commands import (
        CreatePatientPhoneCommand,
        DeletePatientPhoneCommand,
        UpdatePatientPhoneCommand,
    )
    from oralsin_core.core.application.commands.sync_commands import (
        SyncInadimplenciaCommand,
    )
    from oralsin_core.core.application.commands.user_commands import (
        CreateUserCommand,
        DeleteUserCommand,
        UpdateUserCommand,
    )

    # CQRS buses
    from oralsin_core.core.application.cqrs import CommandBusImpl, QueryBusImpl
    from oralsin_core.core.application.handlers.billing_settings_handlers import GetBillingSettingsHandler, ListBillingSettingsHandler, UpdateBillingSettingsHandler

    # Handlers de CRUD (comandos)
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
    from oralsin_core.core.application.handlers.coverage_handlers import (
        RegisterCoverageClinicHandler,
    )
    from oralsin_core.core.application.handlers.dashboard_handlers import (
        GetDashboardReportHandler,
        GetDashboardSummaryHandler,
    )

    # Handlers de Queries (core)
    from oralsin_core.core.application.handlers.query_handlers import (
        GetAddressHandler,
        GetClinicDataHandler,
        GetClinicHandler,
        GetClinicPhoneHandler,
        GetContractHandler,
        GetCoveredClinicHandler,
        GetInstallmentHandler,
        GetPatientHandler,
        GetPatientPhoneHandler,
        GetPaymentMethodsHandler,
        GetUserClinicHandler,
        GetUserHandler,
        ListAddressesHandler,
        ListClinicDataHandler,
        ListClinicPhonesHandler,
        ListClinicsHandler,
        ListContractsHandler,
        ListCoveredClinicsHandler,
        ListInstallmentsHandler,
        ListPatientPhonesHandler,
        ListPatientsHandler,
        ListPaymentMethodsHandler,
        ListUserClinicsHandler,
        ListUsersHandler,
    )

    # Implementações concretas de repositórios
    from oralsin_core.core.application.handlers.sync_handlers import (
        SyncInadimplenciaHandler,
    )

    # Handlers de Queries
    from oralsin_core.core.application.queries.address_queries import GetAddressQuery, ListAddressesQuery
    from oralsin_core.core.application.queries.billing_settings_queries import GetBillingSettingsQuery, ListBillingSettingsQuery
    from oralsin_core.core.application.queries.clinic_data_queries import GetClinicDataQuery, ListClinicDataQuery
    from oralsin_core.core.application.queries.clinic_phone_queries import GetClinicPhoneQuery, ListClinicPhonesQuery
    from oralsin_core.core.application.queries.clinic_queries import GetClinicQuery, ListClinicsQuery
    from oralsin_core.core.application.queries.contract_queries import GetContractQuery, ListContractsQuery
    from oralsin_core.core.application.queries.coverage_queries import ListCoveredClinicsQuery, ListUserClinicsQuery
    from oralsin_core.core.application.queries.covered_clinic_queries import GetCoveredClinicQuery
    from oralsin_core.core.application.queries.dashboard_queries import GetDashboardReportQuery
    from oralsin_core.core.application.queries.installment_queries import GetInstallmentQuery, ListInstallmentsQuery
    from oralsin_core.core.application.queries.patient_phone_queries import GetPatientPhoneQuery, ListPatientPhonesQuery
    from oralsin_core.core.application.queries.patient_queries import GetPatientQuery, ListPatientsQuery
    from oralsin_core.core.application.queries.payment_methods_queries import GetPaymentMethodQuery, ListPaymentMethodsQuery
    from oralsin_core.core.application.queries.user_clinic_queries import GetUserClinicQuery
    from oralsin_core.core.application.queries.user_queries import GetUserQuery, ListUsersQuery
    from oralsin_core.core.application.services.dashboard_pdf_service import DashboardPDFService
    from oralsin_core.core.application.services.dashboard_service import (
        DashboardService,
    )
    from oralsin_core.core.application.services.oralsin_sync_service import (
        OralsinSyncService,
    )
    from oralsin_core.core.domain.mappers.oralsin_payload_mapper import (
        OralsinPayloadMapper,
    )
    from oralsin_core.core.domain.services.formatter_service import (
        FormatterService,
    )

    # ─────────────────────────────────────────────────────────
    # Construção do container DI
    # ─────────────────────────────────────────────────────────
    container = None

    class Container(containers.DeclarativeContainer):
        config = providers.Configuration()
        logo_path = "/app/static/OralsinGestaoInteligenteLogo.png"
        
        # Infra & integração
        logger           = providers.Singleton(structlog.get_logger)
        event_dispatcher = providers.Singleton(
            'oralsin_core.core.domain.services.event_dispatcher.EventDispatcher'
        )

        # CQRS
        command_bus = providers.Singleton(CommandBusImpl, dispatcher=event_dispatcher)
        query_bus   = providers.Singleton(QueryBusImpl)

        # Redis, RabbitMQ, API clients, mappers...
        redis_client        = providers.Singleton(
            redis.Redis,
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
        )
        oralsin_client      = providers.Singleton(OralsinAPIClient)
        oralsin_mapper      = providers.Singleton(OralsinPayloadMapper)

        # Implementações de Repositórios
        address_repo        = providers.Singleton(AddressRepoImpl)
        clinic_repo         = providers.Singleton(ClinicRepoImpl)
        contract_repo       = providers.Singleton(ContractRepoImpl)
        clinic_data_repo    = providers.Singleton(
            ClinicDataRepoImpl,
            address_repo=address_repo,
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
            mapper=oralsin_mapper,
        )
        user_repo           = providers.Singleton(UserRepoImpl)
        user_clinic_repo    = providers.Singleton(UserClinicRepoImpl)
        billing_settings_repo = providers.Singleton(BillingSettingsRepoImpl)
        payment_method_repo = providers.Singleton(PaymentMethodRepoImpl)
        
        collection_case_repo = providers.Singleton(CollectionCaseRepoImpl)
        contact_history_repo = providers.Singleton(ContactHistoryRepoImpl)
        contact_schedule_repo = providers.Singleton(ContactScheduleRepoImpl, 
                                                    installment_repo=installment_repo, 
                                                    billing_settings_repo=billing_settings_repo
                                                    )
        # Hash
        hash_service = providers.Singleton(HashService)

        # Handlers CRUD (comandos)
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

        create_user_handler          = providers.Factory(CreateUserHandler,           repo=user_repo, 
                                                                                      hash_service=hash_service, 
                                                                                      user_clinic_repo=user_clinic_repo
                                                        )
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

        get_billing_settings_handler = providers.Factory( 
            GetBillingSettingsHandler, repo=billing_settings_repo
        )
        list_billing_settings_handler = providers.Factory( 
            ListBillingSettingsHandler, repo=billing_settings_repo
        )
        update_billing_settings_handler = providers.Factory(
            UpdateBillingSettingsHandler, repo=billing_settings_repo
        )
        get_payment_method_handler = providers.Factory( 
            GetPaymentMethodsHandler, repo=payment_method_repo
        )
        list_payment_method_handler = providers.Factory( 
            ListPaymentMethodsHandler, repo=payment_method_repo
        )
    
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
        dashboard_pdf_service = providers.Singleton(
            DashboardPDFService,
            logo_path=logo_path,
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
        dashboard_report_handler = providers.Singleton(
            GetDashboardReportHandler,
            dashboard_service=dashboard_service,
            pdf_service=dashboard_pdf_service,
            user_repo=user_repo,
            user_clinic_repo=user_clinic_repo,
            clinic_repo=clinic_repo,
            clinic_data_repo=clinic_data_repo,
            clinic_phone_repo=clinic_phone_repo,
            collection_case_repo = collection_case_repo,
            contact_history_repo = contact_history_repo,
            contact_schedule_repo = contact_schedule_repo
        )

        # Handlers de Queries (core)
        list_patients_handler            = providers.Factory(ListPatientsHandler,       address_repo=address_repo)
        get_patient_handler              = providers.Factory(GetPatientHandler,         address_repo=address_repo)
        list_addresses_handler           = providers.Factory(ListAddressesHandler)
        get_address_handler              = providers.Factory(GetAddressHandler)
        list_clinics_handler             = providers.Factory(ListClinicsHandler)
        get_clinic_handler               = providers.Factory(GetClinicHandler)
        list_clinic_data_handler         = providers.Factory(ListClinicDataHandler,     address_repo=address_repo)
        get_clinic_data_handler          = providers.Factory(GetClinicDataHandler,      address_repo=address_repo)
        list_clinic_phones_handler       = providers.Factory(ListClinicPhonesHandler)
        get_clinic_phone_handler         = providers.Factory(GetClinicPhoneHandler)
        list_covered_clinics_handler     = providers.Factory(ListCoveredClinicsHandler)
        get_covered_clinic_handler       = providers.Factory(GetCoveredClinicHandler)
        list_contracts_handler           = providers.Factory(ListContractsHandler)
        get_contract_handler             = providers.Factory(GetContractHandler)
        list_installments_handler        = providers.Factory(ListInstallmentsHandler,   mapper=oralsin_mapper)
        get_installment_handler          = providers.Factory(GetInstallmentHandler,     mapper=oralsin_mapper)
        list_patient_phones_handler      = providers.Factory(ListPatientPhonesHandler)
        get_patient_phone_handler        = providers.Factory(GetPatientPhoneHandler)
        list_user_clinics_handler        = providers.Factory(ListUserClinicsHandler)
        get_user_clinic_handler          = providers.Factory(GetUserClinicHandler)
        list_users_handler               = providers.Factory(ListUsersHandler)
        get_user_handler                 = providers.Factory(GetUserHandler)
        
        list_payment_methods_handler     = providers.Factory(ListPaymentMethodsHandler)
        get_payment_methods_handler      = providers.Factory(GetPaymentMethodsHandler)
        
        def init(self):  # noqa: PLR0915
            # Bus de comandos
            cmd_bus = self.command_bus()

            # Registro dos CommandHandlers
            cmd_bus.register(CreateAddressCommand, self.create_address_handler())
            cmd_bus.register(UpdateAddressCommand, self.update_address_handler())
            cmd_bus.register(DeleteAddressCommand, self.delete_address_handler())

            cmd_bus.register(CreateClinicCommand, self.create_clinic_handler())
            cmd_bus.register(UpdateClinicCommand, self.update_clinic_handler())
            cmd_bus.register(DeleteClinicCommand, self.delete_clinic_handler())

            cmd_bus.register(CreateClinicDataCommand, self.create_clinic_data_handler())
            cmd_bus.register(UpdateClinicDataCommand, self.update_clinic_data_handler())

            cmd_bus.register(CreateClinicPhoneCommand, self.create_clinic_phone_handler())
            cmd_bus.register(UpdateClinicPhoneCommand, self.update_clinic_phone_handler())
            cmd_bus.register(DeleteClinicPhoneCommand, self.delete_clinic_phone_handler())

            cmd_bus.register(CreatePatientPhoneCommand, self.create_patient_phone_handler())
            cmd_bus.register(UpdatePatientPhoneCommand, self.update_patient_phone_handler())
            cmd_bus.register(DeletePatientPhoneCommand, self.delete_patient_phone_handler())

            cmd_bus.register(CreateUserCommand, self.create_user_handler())
            cmd_bus.register(UpdateUserCommand, self.update_user_handler())
            cmd_bus.register(DeleteUserCommand, self.delete_user_handler())

            cmd_bus.register(RegisterCoverageClinicCommand, self.register_coverage_clinic_handler())
            cmd_bus.register(LinkUserClinicCommand, self.link_user_clinic_handler())

            cmd_bus.register(SyncInadimplenciaCommand, self.sync_inadimplencia_handler())
            cmd_bus.register(
                UpdateBillingSettingsCommand,
                self.update_billing_settings_handler(),
            )
            # Bus de queries (core)
            qry_bus = self.query_bus()

            qry_bus.register(ListPatientsQuery, self.list_patients_handler())
            qry_bus.register(GetPatientQuery, self.get_patient_handler())

            qry_bus.register(ListAddressesQuery, self.list_addresses_handler())
            qry_bus.register(GetAddressQuery, self.get_address_handler())

            qry_bus.register(ListClinicsQuery, self.list_clinics_handler())
            qry_bus.register(GetClinicQuery, self.get_clinic_handler())

            qry_bus.register(ListClinicDataQuery, self.list_clinic_data_handler())
            qry_bus.register(GetClinicDataQuery, self.get_clinic_data_handler())

            qry_bus.register(ListClinicPhonesQuery, self.list_clinic_phones_handler())
            qry_bus.register(GetClinicPhoneQuery, self.get_clinic_phone_handler())

            qry_bus.register(ListCoveredClinicsQuery, self.list_covered_clinics_handler())
            qry_bus.register(GetCoveredClinicQuery, self.get_covered_clinic_handler())

            qry_bus.register(ListContractsQuery, self.list_contracts_handler())
            qry_bus.register(GetContractQuery, self.get_contract_handler())

            qry_bus.register(ListInstallmentsQuery, self.list_installments_handler())
            qry_bus.register(GetInstallmentQuery, self.get_installment_handler())

            qry_bus.register(ListPatientPhonesQuery, self.list_patient_phones_handler())
            qry_bus.register(GetPatientPhoneQuery, self.get_patient_phone_handler())

            qry_bus.register(ListUserClinicsQuery, self.list_user_clinics_handler())
            qry_bus.register(GetUserClinicQuery, self.get_user_clinic_handler())

            qry_bus.register(ListUsersQuery, self.list_users_handler())
            qry_bus.register(GetUserQuery, self.get_user_handler())
            
            qry_bus.register(ListPaymentMethodsQuery, self.list_payment_methods_handler())
            qry_bus.register(GetPaymentMethodQuery, self.get_payment_methods_handler())
            
            qry_bus.register(
                GetBillingSettingsQuery,
                self.get_billing_settings_handler(),
            )
            qry_bus.register(
                ListBillingSettingsQuery,
                self.list_billing_settings_handler(),
            )
            
            qry_bus.register(GetDashboardReportQuery, self.dashboard_report_handler())

    # ------- INSTANCIAÇÃO E CONFIG -------
    container = Container()
    container.config.rabbitmq_url.from_value(settings.RABBITMQ_URL)
    container.config.redis.host.from_value(settings.REDIS_HOST)
    container.config.redis.port.from_value(settings.REDIS_PORT)
    container.config.redis.db.from_value(settings.REDIS_DB)
    container.config.redis.password.from_value(settings.REDIS_PASSWORD)
    Container.init(container)
    return container
