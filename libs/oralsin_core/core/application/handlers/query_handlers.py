from oralsin_core.adapters.config.composition_root import container as core_container

# ───────────────────────────────────────────────
# Importação dos Repositórios
# ───────────────────────────────────────────────
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
from oralsin_core.core.application.cqrs import PaginatedQueryDTO, QueryBusImpl, QueryHandler

# ───────────────────────────────────────────────
# Importação dos DTOs de consulta
# ───────────────────────────────────────────────
from oralsin_core.core.application.queries.address_queries import (
    GetAddressQuery,
    ListAddressesQuery,
)
from oralsin_core.core.application.queries.clinic_data_queries import (
    GetClinicDataQuery,
    ListClinicDataQuery,
)
from oralsin_core.core.application.queries.clinic_phone_queries import (
    GetClinicPhoneQuery,
    ListClinicPhonesQuery,
)
from oralsin_core.core.application.queries.clinic_queries import (
    GetClinicQuery,
    ListClinicsQuery,
)
from oralsin_core.core.application.queries.contract_queries import (
    GetContractQuery,
    ListContractsQuery,
)
from oralsin_core.core.application.queries.covered_clinic_queries import (
    GetCoveredClinicQuery,
    ListCoveredClinicsQuery,
)
from oralsin_core.core.application.queries.installment_queries import (
    GetInstallmentQuery,
    ListInstallmentsQuery,
)
from oralsin_core.core.application.queries.patient_phone_queries import (
    GetPatientPhoneQuery,
    ListPatientPhonesQuery,
)
from oralsin_core.core.application.queries.patient_queries import (
    GetPatientQuery,
    ListPatientsQuery,
)
from oralsin_core.core.application.queries.user_clinic_queries import (
    GetUserClinicQuery,
    ListUserClinicsQuery,
)
from oralsin_core.core.application.queries.user_queries import (
    GetUserQuery,
    ListUsersQuery,
)
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.address_repository import AddressRepository

# ───────────────────────────────────────────────
# Handlers para Queries do domínio Core
# ───────────────────────────────────────────────

# 1) Pacientes
class ListPatientsHandler(QueryHandler[ListPatientsQuery, PaginatedQueryDTO]):
    def __init__(self, address_repo: AddressRepository):
      self._address_repo = address_repo
      self._repo = PatientRepoImpl(address_repo)

    def handle(self, query: ListPatientsQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetPatientHandler(QueryHandler[GetPatientQuery, object]):
    def __init__(self, address_repo: AddressRepository):
      self._address_repo = address_repo
      self._repo = PatientRepoImpl(address_repo)

    def handle(self, query: GetPatientQuery):
        return self._repo.find_by_id(query.patient_id)

# 2) Endereços
class ListAddressesHandler(QueryHandler[ListAddressesQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = AddressRepoImpl()

    def handle(self, query: ListAddressesQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetAddressHandler(QueryHandler[GetAddressQuery, object]):
    def __init__(self):
        self._repo = AddressRepoImpl()

    def handle(self, query: GetAddressQuery):
        return self._repo.find_by_id(query.id)

# 3) Clínicas
class ListClinicsHandler(QueryHandler[ListClinicsQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = ClinicRepoImpl()

    def handle(self, query: ListClinicsQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetClinicHandler(QueryHandler[GetClinicQuery, object]):
    def __init__(self):
        self._repo = ClinicRepoImpl()

    def handle(self, query: GetClinicQuery):
        return self._repo.find_by_id(query.id)

# 4) Dados complementares de clínica
class ListClinicDataHandler(QueryHandler[ListClinicDataQuery, PaginatedQueryDTO]):
    def __init__(self, address_repo: AddressRepository):
        self._address_repo = address_repo
        self._repo = ClinicDataRepoImpl(address_repo)

    def handle(self, query: ListClinicDataQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetClinicDataHandler(QueryHandler[GetClinicDataQuery, object]):
    def __init__(self, address_repo: AddressRepository):
        self._address_repo = address_repo
        self._repo = ClinicDataRepoImpl(address_repo)

    def handle(self, query: GetClinicDataQuery):
        return self._repo.find_by_id(query.id)

# 5) Telefones de clínica
class ListClinicPhonesHandler(QueryHandler[ListClinicPhonesQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = ClinicPhoneRepoImpl()

    def handle(self, query: ListClinicPhonesQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetClinicPhoneHandler(QueryHandler[GetClinicPhoneQuery, object]):
    def __init__(self):
        self._repo = ClinicPhoneRepoImpl()

    def handle(self, query: GetClinicPhoneQuery):
        return self._repo.find_by_id(query.id)

# 6) Clínicas cobertas
class ListCoveredClinicsHandler(QueryHandler[ListCoveredClinicsQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = CoveredClinicRepoImpl()

    def handle(self, query: ListCoveredClinicsQuery):
        return self._repo.list(
            filtros=query.filtros if hasattr(query, "filtros") else {},
            page=getattr(query, "page", 1),
            page_size=getattr(query, "page_size", 50),
        )

class GetCoveredClinicHandler(QueryHandler[GetCoveredClinicQuery, object]):
    def __init__(self):
        self._repo = CoveredClinicRepoImpl()

    def handle(self, query: GetCoveredClinicQuery):
        return self._repo.find_by_id(query.clinic_id)

# 7) Contratos
class ListContractsHandler(QueryHandler[ListContractsQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = ContractRepoImpl()

    def handle(self, query: ListContractsQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetContractHandler(QueryHandler[GetContractQuery, object]):
    def __init__(self):
        self._repo = ContractRepoImpl()

    def handle(self, query: GetContractQuery):
        return self._repo.find_by_id(query.contract_id)

# 8) Parcelas
class ListInstallmentsHandler(QueryHandler[ListInstallmentsQuery, PaginatedQueryDTO]):
    def __init__(self, mapper: OralsinPayloadMapper):
        self._mapper = mapper
        self._repo = InstallmentRepoImpl(mapper)

    def handle(self, query: ListInstallmentsQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetInstallmentHandler(QueryHandler[GetInstallmentQuery, object]):
    def __init__(self, mapper: OralsinPayloadMapper):
        self._mapper = mapper
        self._repo = InstallmentRepoImpl(mapper)

    def handle(self, query: GetInstallmentQuery):
        return self._repo.find_by_id(query.id)

# 9) Paciente → Telefones de paciente
class ListPatientPhonesHandler(QueryHandler[ListPatientPhonesQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = PatientPhoneRepoImpl()

    def handle(self, query: ListPatientPhonesQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetPatientPhoneHandler(QueryHandler[GetPatientPhoneQuery, object]):
    def __init__(self):
        self._repo = PatientPhoneRepoImpl()

    def handle(self, query: GetPatientPhoneQuery):
        return self._repo.find_by_id(query.id)

# 10) Vínculos Usuário ↔ Clínica
class ListUserClinicsHandler(QueryHandler[ListUserClinicsQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = UserClinicRepoImpl()

    def handle(self, query: ListUserClinicsQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetUserClinicHandler(QueryHandler[GetUserClinicQuery, object]):
    def __init__(self):
        self._repo = UserClinicRepoImpl()

    def handle(self, query: GetUserClinicQuery):
        return self._repo.find_by_id(query.id)

# 11) Usuários
class ListUsersHandler(QueryHandler[ListUsersQuery, PaginatedQueryDTO]):
    def __init__(self):
        self._repo = UserRepoImpl()

    def handle(self, query: ListUsersQuery):
        return self._repo.list(
            filtros=query.filtros,
            page=query.page,
            page_size=query.page_size,
        )

class GetUserHandler(QueryHandler[GetUserQuery, object]):
    def __init__(self):
        self._repo = UserRepoImpl()

    def handle(self, query: GetUserQuery):
        return self._repo.find_by_id(query.user_id)

# ───────────────────────────────────────────────
# Função para registrar todos os handlers nos respectivos QueryBuses
# ───────────────────────────────────────────────

def register_all_query_handlers():
    # Core domain
    core_query_bus: QueryBusImpl = core_container.query_bus()

    core_query_bus.register(ListPatientsQuery, ListPatientsHandler())
    core_query_bus.register(GetPatientQuery, GetPatientHandler())

    core_query_bus.register(ListAddressesQuery, ListAddressesHandler())
    core_query_bus.register(GetAddressQuery, GetAddressHandler())

    core_query_bus.register(ListClinicsQuery, ListClinicsHandler())
    core_query_bus.register(GetClinicQuery, GetClinicHandler())

    core_query_bus.register(ListClinicDataQuery, ListClinicDataHandler())
    core_query_bus.register(GetClinicDataQuery, GetClinicDataHandler())

    core_query_bus.register(ListClinicPhonesQuery, ListClinicPhonesHandler())
    core_query_bus.register(GetClinicPhoneQuery, GetClinicPhoneHandler())

    core_query_bus.register(ListCoveredClinicsQuery, ListCoveredClinicsHandler())
    core_query_bus.register(GetCoveredClinicQuery, GetCoveredClinicHandler())

    core_query_bus.register(ListContractsQuery, ListContractsHandler())
    core_query_bus.register(GetContractQuery, GetContractHandler())

    core_query_bus.register(ListInstallmentsQuery, ListInstallmentsHandler())
    core_query_bus.register(GetInstallmentQuery, GetInstallmentHandler())

    core_query_bus.register(ListPatientPhonesQuery, ListPatientPhonesHandler())
    core_query_bus.register(GetPatientPhoneQuery, GetPatientPhoneHandler())

    core_query_bus.register(ListUserClinicsQuery, ListUserClinicsHandler())
    core_query_bus.register(GetUserClinicQuery, GetUserClinicHandler())

    core_query_bus.register(ListUsersQuery, ListUsersHandler())
    core_query_bus.register(GetUserQuery, GetUserHandler())