# ╭────────────────────────────────────────────────────────────────────────────╮
# │  ViewSets REST – Domínios Core (Oralsin) + Billing (Notification-Billing) │
# │                                                                            │
# │  • Filtro seguro   → remove “page” / “page_size” antes de passar ao repo   │
# │  • Paginação DRY   → mix-in centralizado                                   │
# │  • Cache em LIST / RETRIEVE                                                │
# │  • Métrica trace   → decorator `track_http`                                │
# ╰────────────────────────────────────────────────────────────────────────────╯
from __future__ import annotations

import math

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from oralsin_core.adapters.config.composition_root import container as core_container
from oralsin_core.adapters.observability.decorators import track_http

# ───────────────────────────────  CQRS Buses  ────────────────────────────────
from oralsin_core.core.application.cqrs import CommandBusImpl, QueryBusImpl
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from notification_billing.adapters.config.composition_root import (
    container as billing_container,
)
from plugins.django_interface.permissions import IsAdminUser, IsClinicUser

# ────────────────────────────────  Serializers  ───────────────────────────────
from ..serializers.core_serializers import (
    AddressSerializer,
    ClinicDataSerializer,
    ClinicPhoneSerializer,
    ClinicSerializer,
    ContactHistorySerializer,
    ContactScheduleSerializer,
    ContractSerializer,
    CoveredClinicSerializer,
    InstallmentSerializer,
    MessageSerializer,
    PatientPhoneSerializer,
    PatientSerializer,
    UserClinicSerializer,
    UserSerializer,
)

core_command_bus: CommandBusImpl = core_container.command_bus()
core_query_bus: QueryBusImpl = core_container.query_bus()
billing_command_bus: CommandBusImpl = billing_container.command_bus()
billing_query_bus: QueryBusImpl = billing_container.query_bus()

# ───────────────────────────────  Constantes  ────────────────────────────────
LIST_TTL = 5 * 60        # 5 min
RETRIEVE_TTL = 10 * 60   # 10 min
DEFAULT_PAGE_SIZE = 50

# ╭──────────────────────────────────────────────────────────────────────────╮
# │ Helper mix-in – paginação + filtros                                      │
# ╰──────────────────────────────────────────────────────────────────────────╯
class PaginationFilterMixin:
    """Remove page/page_size do QueryDict e devolve filtros limpos."""

    @staticmethod
    def _pagination(request) -> tuple[int, int]:
        page = int(request.query_params.get("page", 1))
        size = int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE))
        return page, size

    @staticmethod
    def _filters(request) -> dict[str, str]:
        params = request.query_params.copy()  # QueryDict → mutável
        params.pop("page", None)
        params.pop("page_size", None)
        return params.dict()


# ────────────────────────────────
# Imports de Commands / DTOs / Queries
# (agrupados abaixo para clareza; sem impacto em runtime)
# ────────────────────────────────
from oralsin_core.core.application.commands.address_commands import (  # noqa: E402
    CreateAddressCommand,
    DeleteAddressCommand,
    UpdateAddressCommand,
)
from oralsin_core.core.application.commands.clinic_commands import (  # noqa: E402
    CreateClinicCommand,
    DeleteClinicCommand,
    UpdateClinicCommand,
)
from oralsin_core.core.application.commands.clinic_data_commands import (  # noqa: E402
    CreateClinicDataCommand,
    UpdateClinicDataCommand,
)
from oralsin_core.core.application.commands.clinic_phone_commands import (  # noqa: E402
    CreateClinicPhoneCommand,
    DeleteClinicPhoneCommand,
    UpdateClinicPhoneCommand,
)
from oralsin_core.core.application.commands.covered_clinic_commands import (  # noqa: E402
    RegisterCoveredClinicCommand,
)
from oralsin_core.core.application.commands.patient_commands import (  # noqa: E402
    RegisterPatientsCommand,
    UpdatePatientCommand,
)
from oralsin_core.core.application.commands.patient_phone_commands import (  # noqa: E402
    CreatePatientPhoneCommand,
    DeletePatientPhoneCommand,
    UpdatePatientPhoneCommand,
)
from oralsin_core.core.application.commands.user_commands import (  # noqa: E402
    CreateUserCommand,
    DeleteUserCommand,
    UpdateUserCommand,
)
from oralsin_core.core.application.dtos.address_dto import AddressDTO  # noqa: E402
from oralsin_core.core.application.dtos.clinic_data_dto import ClinicDataDTO  # noqa: E402
from oralsin_core.core.application.dtos.clinic_dto import ClinicDTO  # noqa: E402
from oralsin_core.core.application.dtos.clinic_phone_dto import ClinicPhoneDTO  # noqa: E402
from oralsin_core.core.application.dtos.covered_clinic_dto import (  # noqa: E402
    CoveredClinicCreateDTO,
)
from oralsin_core.core.application.dtos.patient_dto import (  # noqa: E402
    RegisterPatientsDTO,
    UpdatePatientDTO,
)
from oralsin_core.core.application.dtos.patient_phone_dto import PatientPhoneDTO  # noqa: E402
from oralsin_core.core.application.dtos.user_dto import (  # noqa: E402
    CreateUserDTO,
    UpdateUserDTO,
)
from oralsin_core.core.application.queries.address_queries import (  # noqa: E402
    GetAddressQuery,
    ListAddressesQuery,
)
from oralsin_core.core.application.queries.clinic_data_queries import (  # noqa: E402
    GetClinicDataQuery,
    ListClinicDataQuery,
)
from oralsin_core.core.application.queries.clinic_phone_queries import (  # noqa: E402
    GetClinicPhoneQuery,
    ListClinicPhonesQuery,
)
from oralsin_core.core.application.queries.clinic_queries import (  # noqa: E402
    GetClinicQuery,
    ListClinicsQuery,
)
from oralsin_core.core.application.queries.contract_queries import (  # noqa: E402
    GetContractQuery,
    ListContractsQuery,
)
from oralsin_core.core.application.queries.covered_clinic_queries import (  # noqa: E402
    GetCoveredClinicQuery,
    ListCoveredClinicsQuery,
)
from oralsin_core.core.application.queries.installment_queries import (  # noqa: E402
    GetInstallmentQuery,
    ListInstallmentsQuery,
)
from oralsin_core.core.application.queries.patient_phone_queries import (  # noqa: E402
    GetPatientPhoneQuery,
    ListPatientPhonesQuery,
)
from oralsin_core.core.application.queries.patient_queries import (  # noqa: E402
    GetPatientQuery,
    ListPatientsQuery,
)
from oralsin_core.core.application.queries.user_clinic_queries import (  # noqa: E402
    GetUserClinicQuery,
    ListUserClinicsQuery,
)
from oralsin_core.core.application.queries.user_queries import (  # noqa: E402
    GetUserQuery,
    ListUsersQuery,
)

from notification_billing.core.application.commands.contact_schedule_commands import (  # noqa: E402
    CreateContactScheduleCommand,
    DeleteContactScheduleCommand,
    UpdateContactScheduleCommand,
)
from notification_billing.core.application.commands.message_commands import (  # noqa: E402
    CreateMessageCommand,
    DeleteMessageCommand,
    UpdateMessageCommand,
)
from notification_billing.core.application.dtos.message_dto import MessageDTO  # noqa: E402
from notification_billing.core.application.dtos.schedule_dto import (  # noqa: E402
    ContactScheduleDTO,
)
from notification_billing.core.application.queries.contact_history_queries import (  # noqa: E402
    GetContactHistoryQuery,
    ListContactHistoryQuery,
)
from notification_billing.core.application.queries.contact_queries import (  # noqa: E402
    ListDueContactsQuery,
)
from notification_billing.core.application.queries.contact_schedule_queries import (  # noqa: E402
    GetContactScheduleQuery,
)
from notification_billing.core.application.queries.message_queries import (  # noqa: E402
    GetMessageQuery,
    ListMessagesQuery,
)


# ===========================================================================
# Cache Helper: gera um key_prefix incluindo o clinic_id do usuário
# ===========================================================================
def cache_key_prefix_for(prefix: str):
    def _key(request, *args, **kwargs):
        clinic_id = getattr(request.user, "clinic_id", "anon")
        return f"{prefix}_clinic_{clinic_id}"
    return _key

# ╭──────────────────────────────────────────────╮
# │  Core Domain ViewSets                        │
# ╰──────────────────────────────────────────────╯
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("patients_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("patient_detail")),
    name="retrieve",
)
class PatientViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("PatientViewSet_list")
    def list(self, request):
        # Extrai filtros e parâmetros de paginação (page, page_size) da requisição
        filtros = self._filters(request)
        page, page_size = self._pagination(request)

        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        
        # Dispara a query para obter os pacientes paginados
        q = ListPatientsQuery(filtros=filtros, page=page, page_size=page_size)
        res = core_query_bus.dispatch(q)
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        pacientes_serializados = PatientSerializer(res.items, many=True).data

        payload = {
            "results": pacientes_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("PatientViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        pat = core_query_bus.dispatch(GetPatientQuery(filtros=filtros, patient_id=str(pk)))
        return Response(PatientSerializer(pat).data)

    @track_http("PatientViewSet_update")
    def update(self, request, pk=None):
        dto = UpdatePatientDTO(**request.data)
        pat = core_command_bus.dispatch(UpdatePatientCommand(id=pk, payload=dto))
        return Response(PatientSerializer(pat).data)

    @track_http("PatientViewSet_sync")
    @action(detail=False, methods=["post"])
    def sync(self, request):
        dto = RegisterPatientsDTO(
            user_id=str(request.user.id),
            initial_due_date=request.data.get("initial_due_date"),
            final_due_date=request.data.get("final_due_date"),
        )
        res = core_command_bus.dispatch(RegisterPatientsCommand(payload=dto))
        return Response({"message": "Sync iniciado", "result": res})


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("addresses_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("address_detail")),
    name="retrieve",
)
class AddressViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("AddressViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
            
        res = core_query_bus.dispatch(ListAddressesQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        enderecos_serializados = AddressSerializer(res.items, many=True).data

        payload = {
            "results": enderecos_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("AddressViewSet_retrieve")
    def retrieve(self, request, pk=None):
        addr = core_query_bus.dispatch(GetAddressQuery(id=str(pk)))
        return Response(AddressSerializer(addr).data)

    @track_http("AddressViewSet_create")
    def create(self, request):
        addr = core_command_bus.dispatch(CreateAddressCommand(payload=AddressDTO(**request.data)))
        return Response(AddressSerializer(addr).data, status=status.HTTP_201_CREATED)

    @track_http("AddressViewSet_update")
    def update(self, request, pk=None):
        addr = core_command_bus.dispatch(UpdateAddressCommand(id=pk, payload=AddressDTO(**request.data)))
        return Response(AddressSerializer(addr).data)

    @track_http("AddressViewSet_destroy")
    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeleteAddressCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("clinics_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("clinic_detail")),
    name="retrieve",
)
class ClinicViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @track_http("ClinicViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = core_query_bus.dispatch(ListClinicsQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        clinicas_serializadas = ClinicSerializer(res.items, many=True).data

        payload = {
            "results": clinicas_serializadas,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)
    
    @track_http("ClinicViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        c = core_query_bus.dispatch(GetClinicQuery(filtros=filtros, id=str(pk)))
        return Response(ClinicSerializer(c).data)

    @track_http("ClinicViewSet_create")
    def create(self, request):
        c = core_command_bus.dispatch(CreateClinicCommand(payload=ClinicDTO(**request.data)))
        return Response(ClinicSerializer(c).data, status=status.HTTP_201_CREATED)

    @track_http("ClinicViewSet_update")
    def update(self, request, pk=None):
        c = core_command_bus.dispatch(UpdateClinicCommand(id=pk, payload=ClinicDTO(**request.data)))
        return Response(ClinicSerializer(c).data)

    @track_http("ClinicViewSet_destroy")
    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeleteClinicCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("clinica_datas_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("clinica_data_detail")),
    name="retrieve",
)
class ClinicDataViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("ClinicDataViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        if getattr(request.user, "role", None) == "clinic":
            filtros["clinic_id"] = request.user.clinic_id
            
        res = core_query_bus.dispatch(ListClinicDataQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        dados_clinicas_serializadas = ClinicDataSerializer(res.items, many=True).data

        payload = {
            "results": dados_clinicas_serializadas,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("ClinicDataViewSet_retrieve")
    def retrieve(self, request, pk=None):
        cd = core_query_bus.dispatch(GetClinicDataQuery(id=str(pk)))
        return Response(ClinicDataSerializer(cd).data)

    @track_http("ClinicDataViewSet_create")
    def create(self, request):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        cd = core_command_bus.dispatch(CreateClinicDataCommand(payload=ClinicDataDTO(**payload)))
        return Response(ClinicDataSerializer(cd).data, status=status.HTTP_201_CREATED)

    @track_http("ClinicDataViewSet_update")
    def update(self, request, pk=None):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        cd = core_command_bus.dispatch(UpdateClinicDataCommand(id=pk, payload=ClinicDataDTO(**payload)))
        return Response(ClinicDataSerializer(cd).data)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("clinic_phones_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("clinic_phone_detail")),
    name="retrieve",
)
class ClinicPhoneViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("ClinicPhoneViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        if getattr(request.user, "role", None) == "clinic":
            filtros["clinic_id"] = request.user.clinic_id
            
        res = core_query_bus.dispatch(ListClinicPhonesQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        telefones_clinicas_serializadas = ClinicPhoneSerializer(res.items, many=True).data

        payload = {
            "results": telefones_clinicas_serializadas,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)
    
    @track_http("ClinicPhoneViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        cp = core_query_bus.dispatch(GetClinicPhoneQuery(filtros=filtros, id=str(pk)))
        return Response(ClinicPhoneSerializer(cp).data)

    @track_http("ClinicPhoneViewSet_create")
    def create(self, request):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        cp = core_command_bus.dispatch(CreateClinicPhoneCommand(payload=ClinicPhoneDTO(**payload)))
        return Response(ClinicPhoneSerializer(cp).data, status=status.HTTP_201_CREATED)

    @track_http("ClinicPhoneViewSet_update")
    def update(self, request, pk=None):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        cp = core_command_bus.dispatch(UpdateClinicPhoneCommand(id=pk, payload=ClinicPhoneDTO(**payload)))
        return Response(ClinicPhoneSerializer(cp).data)

    @track_http("ClinicPhoneViewSet_destroy")
    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeleteClinicPhoneCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("covered_clinics_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("covered_clinic_detail")),
    name="retrieve",
)
class CoveredClinicViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("CoveredClinicViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = core_query_bus.dispatch(ListCoveredClinicsQuery(filtros=filtros))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        clinicas_cobertas_serializadas = CoveredClinicSerializer(res.items, many=True).data

        payload = {
            "results": clinicas_cobertas_serializadas,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("CoveredClinicViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        cov = core_query_bus.dispatch(GetCoveredClinicQuery(filtros=filtros, clinic_id=str(pk)))
        return Response(CoveredClinicSerializer(cov).data)

    @track_http("CoveredClinicViewSet_create")
    def create(self, request):
        cov = core_command_bus.dispatch(RegisterCoveredClinicCommand(payload=CoveredClinicCreateDTO(**request.data)))
        return Response(CoveredClinicSerializer(cov).data, status=status.HTTP_201_CREATED)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("patient_phones_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("patient_phone_detail")),
    name="retrieve",
)
class PatientPhoneViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("PatientPhoneViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = core_query_bus.dispatch(ListPatientPhonesQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        telefones_pacientes_serializados = PatientPhoneSerializer(res.items, many=True).data

        payload = {
            "results": telefones_pacientes_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("PatientPhoneViewSet_retrieve")
    def retrieve(self, request, pk=None):
        pp = core_query_bus.dispatch(GetPatientPhoneQuery(filtros={}, id=str(pk)))
        return Response(PatientPhoneSerializer(pp).data)

    @track_http("PatientPhoneViewSet_create")
    def create(self, request):
        pp = core_command_bus.dispatch(CreatePatientPhoneCommand(payload=PatientPhoneDTO(**request.data)))
        return Response(PatientPhoneSerializer(pp).data, status=status.HTTP_201_CREATED)

    @track_http("PatientPhoneViewSet_update")
    def update(self, request, pk=None):
        pp = core_command_bus.dispatch(UpdatePatientPhoneCommand(id=pk, payload=PatientPhoneDTO(**request.data)))
        return Response(PatientPhoneSerializer(pp).data)

    @track_http("PatientPhoneViewSet_destroy")
    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeletePatientPhoneCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("contracts_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("contract_detail")),
    name="retrieve",
)
class ContractViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("ContractViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
            
        res = core_query_bus.dispatch(ListContractsQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        contratos_serializados = ContractSerializer(res.items, many=True).data

        payload = {
            "results": contratos_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)
    
    @track_http("ContractViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        ctr = core_query_bus.dispatch(GetContractQuery(filtros=filtros, contract_id=str(pk)))
        return Response(ContractSerializer(ctr).data)

    @track_http("ContractViewSet_installments")
    @action(detail=True, methods=["get"])
    def installments(self, request, pk=None):
        from oralsin_core.core.application.dtos.contract_dto import ContractQueryDTO
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        q = ListInstallmentsQuery(
            filtros=filtros,
            payload=ContractQueryDTO(contract_id=str(pk)),
            page=page,
            page_size=page_size,
        )
        res = core_query_bus.dispatch(q)
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        contratos_serializados = InstallmentSerializer(res.items, many=True).data
        payload = {
            "results": contratos_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }
                
        return Response(payload, status=status.HTTP_200_OK)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("installments_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("cinstallment_detail")),
    name="retrieve",
)
class InstallmentViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("InstallmentViewSet_list")
    def list(self, request):
        from oralsin_core.core.application.dtos.contract_dto import ContractQueryDTO
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        contract_id = filtros.pop("contract_id", "")
        
        q = ListInstallmentsQuery(
            filtros=filtros,
            payload=ContractQueryDTO(contract_id=contract_id),
            page=page,
            page_size=page_size,
        )
        res = core_query_bus.dispatch(q)
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        parcelas_serializadas = InstallmentSerializer(res.items, many=True).data
        payload = {
            "results": parcelas_serializadas,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }
        
        return Response(payload, status=status.HTTP_200_OK)

    @track_http("InstallmentViewSet_retrieve")
    def retrieve(self, request, pk=None):
        inst = core_query_bus.dispatch(GetInstallmentQuery(filtros={}, id=str(pk)))
        return Response(InstallmentSerializer(inst).data)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("user_clinics_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("user_clinic_detail")),
    name="retrieve",
)
class UserClinicViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @track_http("UserClinicViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = core_query_bus.dispatch(ListUserClinicsQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        usuarios_clinicas_serializados = UserClinicSerializer(res.items, many=True).data

        payload = {
            "results": usuarios_clinicas_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("UserClinicViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        uc = core_query_bus.dispatch(GetUserClinicQuery(filtros=filtros, id=str(pk)))
        return Response(UserClinicSerializer(uc).data)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("users_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("user_detail")),
    name="retrieve",
)
class UserViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @track_http("UserViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = core_query_bus.dispatch(ListUsersQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        usuarios_serializados = UserSerializer(res.items, many=True).data

        payload = {
            "results": usuarios_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("UserViewSet_retrieve")
    def retrieve(self, request, pk=None):
        user = core_query_bus.dispatch(GetUserQuery(filtros={}, user_id=str(pk)))
        return Response(UserSerializer(user).data)

    @track_http("UserViewSet_create")
    def create(self, request):
        dto = CreateUserDTO(**request.data)
        user = core_command_bus.dispatch(CreateUserCommand(payload=dto))

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @track_http("UserViewSet_update")
    def update(self, request, pk=None):
        user = core_command_bus.dispatch(UpdateUserCommand(id=pk, payload=UpdateUserDTO(**request.data)))
        return Response(UserSerializer(user).data)

    @track_http("UserViewSet_destroy")
    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeleteUserCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ╭──────────────────────────────────────────────╮
# │  Billing Domain ViewSets                     │
# ╰──────────────────────────────────────────────╯
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("contact_schedules_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("contact_schedule_detail")),
    name="retrieve",
)
class ContactScheduleViewSet(PaginationFilterMixin, viewsets.ViewSet):
    """Agendamentos de contato."""
    permission_classes = [IsClinicUser]

    @track_http("ContactScheduleViewSet_list")
    def list(self, request):
        filtros = {"clinic_id": request.user.clinic_id, **self._filters(request)}
        page, page_size = self._pagination(request)
        
        res = billing_query_bus.dispatch(ListDueContactsQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        agendamentos_serializados = ContactScheduleSerializer(res.items, many=True).data

        payload = {
            "results": agendamentos_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)
    
    @track_http("ContactScheduleViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        # Se o usuário for do tipo "clinic", força o filtro por clinic_id
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)
        cs = billing_query_bus.dispatch(GetContactScheduleQuery(filtros=filtros, id=str(pk)))
        return Response(ContactScheduleSerializer(cs).data)

    @track_http("ContactScheduleViewSet_create")
    def create(self, request):
        cs = billing_command_bus.dispatch(CreateContactScheduleCommand(payload=ContactScheduleDTO(**request.data)))
        return Response(ContactScheduleSerializer(cs).data, status=status.HTTP_201_CREATED)

    @track_http("ContactScheduleViewSet_update")
    def update(self, request, pk=None):
        cs = billing_command_bus.dispatch(UpdateContactScheduleCommand(id=pk, payload=ContactScheduleDTO(**request.data)))
        return Response(ContactScheduleSerializer(cs).data)

    @track_http("ContactScheduleViewSet_destroy")
    def destroy(self, request, pk=None):
        billing_command_bus.dispatch(DeleteContactScheduleCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("contact_histories_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("contact_history_detail")),
    name="retrieve",
)
class ContactHistoryViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("ContactHistoryViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = billing_query_bus.dispatch(ListContactHistoryQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        historicos_serializados = ContactHistorySerializer(res.items, many=True).data

        payload = {
            "results": historicos_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("ContactHistoryViewSet_retrieve")
    def retrieve(self, request, pk=None):
        ch = billing_query_bus.dispatch(GetContactHistoryQuery(filtros={}, id=str(pk)))
        return Response(ContactHistorySerializer(ch).data)


# ───────────────────────────────────────────────────────────────────────────
@method_decorator(
    cache_page(LIST_TTL, key_prefix=cache_key_prefix_for("messages_list")),
    name="list",
)
@method_decorator(
    cache_page(RETRIEVE_TTL, key_prefix=cache_key_prefix_for("message_detail")),
    name="retrieve",
)
class MessageViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("MessageViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = billing_query_bus.dispatch(ListMessagesQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        mensagens_serializadas = MessageSerializer(res.items, many=True).data

        payload = {
            "results": mensagens_serializadas,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("MessageViewSet_retrieve")
    def retrieve(self, request, pk=None): 
        m = billing_query_bus.dispatch(GetMessageQuery(filtros={}, id=str(pk)))
        return Response(MessageSerializer(m).data)

    @track_http("MessageViewSet_create")
    def create(self, request):
        m = billing_command_bus.dispatch(CreateMessageCommand(payload=MessageDTO(**request.data)))
        return Response(MessageSerializer(m).data, status=status.HTTP_201_CREATED)

    @track_http("MessageViewSet_update")
    def update(self, request, pk=None):
        m = billing_command_bus.dispatch(UpdateMessageCommand(id=pk, payload=MessageDTO(**request.data)))
        return Response(MessageSerializer(m).data)

    @track_http("MessageViewSet_destroy")
    def destroy(self, request, pk=None):
        billing_command_bus.dispatch(DeleteMessageCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
