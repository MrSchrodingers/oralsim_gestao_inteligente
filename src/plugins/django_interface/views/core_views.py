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
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Avg, DecimalField, FloatField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from oralsin_core.adapters.config.composition_root import container as core_container
from oralsin_core.adapters.observability.decorators import track_http
from oralsin_core.core.application.commands.billing_settings_commands import UpdateBillingSettingsCommand
from oralsin_core.core.application.commands.registration_request_commands import ApproveRegistrationRequestCommand, CreateRegistrationRequestCommand, RejectRegistrationRequestCommand
from oralsin_core.core.application.cqrs import CommandBusImpl, QueryBusImpl
from oralsin_core.core.application.dtos.registration_request_dto import CreateRegistrationRequestDTO
from oralsin_core.core.application.handlers.registration_request_handlers import FERNET
from oralsin_core.core.application.queries.billing_settings_queries import GetBillingSettingsQuery, ListBillingSettingsQuery
from oralsin_core.core.application.queries.payment_methods_queries import GetPaymentMethodQuery, ListPaymentMethodsQuery
from oralsin_core.core.application.queries.registration_request_queries import GetRegistrationRequestQuery, ListRegistrationRequestsQuery
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from cordial_billing.adapters.config.composition_root import (
    container as cordial_billing_container,
)
from cordial_billing.core.application.commands.create_deal_command import CreatePipedriveDealCommand
from cordial_billing.core.application.queries.collection_case_queries import GetCollectionCaseQuery, ListCollectionCasesQuery
from notification_billing.adapters.config.composition_root import (
    container as notification_billing_container,
)

# ───────────────────────────────  CQRS Buses  ────────────────────────────────
from notification_billing.core.application.commands.pending_call_commands import SetPendingCallDoneCommand
from notification_billing.core.application.queries.flow_step_config_queries import GetFlowStepConfigQuery, ListFlowStepConfigsQuery
from notification_billing.core.application.queries.pending_call_queries import GetPendingCallQuery, ListPendingCallsQuery
from plugins.django_interface.models import Message as MessageModel
from plugins.django_interface.models import Patient as PatientModel
from plugins.django_interface.models import PendingCall as PendingCallModel
from plugins.django_interface.models import User
from plugins.django_interface.permissions import IsAdminUser, IsClinicUser

# ────────────────────────────────  Serializers  ───────────────────────────────
from ..serializers.core_serializers import (
    AddressSerializer,
    BillingSettingsSerializer,
    ClinicDataSerializer,
    ClinicPhoneSerializer,
    ClinicSerializer,
    CollectionCaseSerializer,
    ContactHistorySerializer,
    ContactScheduleSerializer,
    ContractSerializer,
    CoveredClinicSerializer,
    FlowStepConfigSerializer,
    InstallmentSerializer,
    MessageSerializer,
    PatientPhoneSerializer,
    PatientSerializer,
    PaymentMethodSerializer,
    PendingCallSerializer,
    RegistrationRequestSerializer,
    UserClinicSerializer,
    UserFullDataSerializer,
    UserSerializer,
)

core_command_bus: CommandBusImpl = core_container.command_bus()
core_query_bus: QueryBusImpl = core_container.query_bus()
notification_billing_command_bus: CommandBusImpl = notification_billing_container.command_bus()
notification_billing_query_bus: QueryBusImpl = notification_billing_container.query_bus()
cordial_billing_command_bus: CommandBusImpl = cordial_billing_container.command_bus()
cordial_billing_query_bus: QueryBusImpl = cordial_billing_container.query_bus()

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
        params = request.query_params.copy()          # QueryDict mutável
        params.pop("page", None)
        params.pop("page_size", None)

        clean: dict[str, any] = {}
        for key in params:
            values = params.getlist(key)          
            if key.endswith("__in"):
                items: list[str] = []
                for v in values:
                    items.extend(v.split(","))        # “a,b,c” → [a,b,c]
                clean[key] = items
            else:
                clean[key] = values[0] if len(values) == 1 else values

        return clean


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
    """
    Gera um prefixo do tipo:
      {prefix}_clinic_{id}_v{version}
    onde `version` é um inteiro armazenado em cache e
    incrementado sempre que houver update.
    """
    def _key(request, *args, **kwargs):
        clinic_id = getattr(request.user, "clinic_id", "anon")
        version_key = f"{prefix}_v_clinic_{clinic_id}"
        version = cache.get(version_key) or 0
        return f"{prefix}_clinic_{clinic_id}_v{version}"
    return _key

# ╭──────────────────────────────────────────────╮
# │  Core Domain ViewSets                        │
# ╰──────────────────────────────────────────────╯

class PatientViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("PatientViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)

        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)

        flow_type = filtros.pop("flow_type", None)
        search = filtros.pop("search", "").strip()
        
        base_qs = PatientModel.objects.prefetch_related("contracts")

        # ────────── 1) QUERYSET bruto para o summary ────────────────────
        qs = base_qs.filter(**filtros)

        summary = {
                "with_receivable": qs
                    .filter(schedules__isnull=False)
                    .exclude(collectioncase__isnull=False)
                    .values("id")
                    .distinct()
                    .count(),

                "with_collection": qs
                    .filter(collectioncase__isnull=False)
                    .exclude(schedules__isnull=False)
                    .values("id")
                    .distinct()
                    .count(),
            }
        
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(cpf__icontains=search)  |
                Q(email__icontains=search)
            )
        if flow_type == "notification_billing":
            qs = qs.filter(schedules__isnull=False).exclude(collectioncase__isnull=False)
        elif flow_type == "cordial_billing":
            qs = qs.filter(collectioncase__isnull=False)

        # ────────── 2) página paginada pelo CQRS ────────────────────
        filtros_for_query = {**filtros, **({"flow_type": flow_type} if flow_type else {})}
        res = core_query_bus.dispatch(
            ListPatientsQuery(filtros=filtros_for_query, page=page, page_size=page_size)
        )

        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size else 1
        
        pacientes_serializados = PatientSerializer(res.items, many=True).data

        payload = {
            "results": pacientes_serializados,
            "total_items": total_items,
            "summary": summary,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
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
        pp = core_query_bus.dispatch(GetPatientPhoneQuery(id=str(pk)))
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
        # extrai e renomeia para usar no filtros que vai pro repositório
        contract_uuid = filtros.pop("contract_id", None)
        if contract_uuid:
            filtros["contract_id"] = contract_uuid
        
        q = ListInstallmentsQuery(
            filtros=filtros,
            payload=ContractQueryDTO(contract_id=contract_uuid),
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
        """
        Retorna um único usuário com
        - clínicas associadas,
        - endereço,
        - telefones,
        usando o serializer expandido.
        """
        user = get_object_or_404(
        User.objects.prefetch_related(
                "clinics__clinic__data__address",
                "clinics__clinic__phones",
            ),
            pk=pk,
        )
        serializer = UserFullDataSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
class ContactScheduleViewSet(PaginationFilterMixin, viewsets.ViewSet):
    """Agendamentos de contato."""
    permission_classes = [IsClinicUser]

    @track_http("ContactScheduleViewSet_list")
    def list(self, request):
        filtros = {"clinic_id": request.user.clinic_id, **self._filters(request)}
        page, page_size = self._pagination(request)
        
        res = notification_billing_query_bus.dispatch(ListDueContactsQuery(filtros=filtros, page=page, page_size=page_size))
        
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
        cs = notification_billing_query_bus.dispatch(GetContactScheduleQuery(filtros=filtros, id=str(pk)))
        return Response(ContactScheduleSerializer(cs).data)

    @track_http("ContactScheduleViewSet_create")
    def create(self, request):
        cs = notification_billing_command_bus.dispatch(CreateContactScheduleCommand(payload=ContactScheduleDTO(**request.data)))
        return Response(ContactScheduleSerializer(cs).data, status=status.HTTP_201_CREATED)

    @track_http("ContactScheduleViewSet_update")
    def update(self, request, pk=None):
        cs = notification_billing_command_bus.dispatch(UpdateContactScheduleCommand(id=pk, payload=ContactScheduleDTO(**request.data)))
        return Response(ContactScheduleSerializer(cs).data)

    @track_http("ContactScheduleViewSet_destroy")
    def destroy(self, request, pk=None):
        notification_billing_command_bus.dispatch(DeleteContactScheduleCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ───────────────────────────────────────────────────────────────────────────
class ContactHistoryViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("ContactHistoryViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = notification_billing_query_bus.dispatch(ListContactHistoryQuery(filtros=filtros, page=page, page_size=page_size))
        
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
        ch = notification_billing_query_bus.dispatch(GetContactHistoryQuery(filtros={}, id=str(pk)))
        return Response(ContactHistorySerializer(ch).data)


# ───────────────────────────────────────────────────────────────────────────
class MessageViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    @track_http("MessageViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        
        res = notification_billing_query_bus.dispatch(ListMessagesQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        mensagens_serializadas = MessageSerializer(res.items, many=True).data
        
        # ────────── 1) QUERYSET bruto só para o summary ────────────────────
        qs = MessageModel.objects.filter(**filtros)
        summary = {
            "whatsapp": qs.filter(type="whatsapp").count(),
            "sms": qs.filter(type="sms").count(),
            "email": qs.filter(type="email").count(),
        }

        payload = {
            "results": mensagens_serializadas,     
            "total_items": total_items,
            "summary": summary,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    @track_http("MessageViewSet_retrieve")
    def retrieve(self, request, pk=None): 
        filtros = self._filters(request)
        m = notification_billing_query_bus.dispatch(GetMessageQuery(filtros=filtros, message_id=str(pk)))
        return Response(MessageSerializer(m).data)

    @track_http("MessageViewSet_create")
    def create(self, request):
        m = notification_billing_command_bus.dispatch(CreateMessageCommand(payload=MessageDTO(**request.data)))
        return Response(MessageSerializer(m).data, status=status.HTTP_201_CREATED)

    @track_http("MessageViewSet_update")
    def update(self, request, pk=None):
        m = notification_billing_command_bus.dispatch(UpdateMessageCommand(id=pk, payload=MessageDTO(**request.data)))
        return Response(MessageSerializer(m).data)

    @track_http("MessageViewSet_destroy")
    def destroy(self, request, pk=None):
        notification_billing_command_bus.dispatch(DeleteMessageCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PendingCallViewSet(PaginationFilterMixin, viewsets.ViewSet):
    """
    Ligações pendentes (phonecall).  
    • Somente leitura para list/retrieve;  
    • Ação `mark_done` para encerrar a pendência.
    """

    permission_classes = [IsClinicUser]

    # ------------------------------------------------------------------ #
    @track_http("PendingCallViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)

        # sempre força clinic_id do usuário-clínica
        filtros["clinic_id"] = str(request.user.clinic_id)

        res = notification_billing_query_bus.dispatch(
            ListPendingCallsQuery(filtros=filtros, page=page, page_size=page_size)
        )

        qs = PendingCallModel.objects.filter(**filtros).select_related("patient", "contract").prefetch_related("patient__phones")

        summary = {
            "high": qs.filter(Q(attempts__gte=2) | Q(contract__overdue_amount__gt=1000)).count(),
            "medium": qs.filter(
                (Q(attempts__gte=1, attempts__lt=2))
                | (Q(contract__overdue_amount__gt=500) & Q(contract__overdue_amount__lte=1000))
            ).count(),
            "normal": qs.filter(attempts=0, contract__overdue_amount__lte=500).count(),
            "total_overdue": str(
                qs.aggregate(
                    total=Coalesce(
                        Sum("contract__overdue_amount"),
                        Value(
                            Decimal("0.00"),
                            output_field=DecimalField(max_digits=14, decimal_places=2),
                        ),
                    )
                )["total"]
            ),
            "avg_attempts": float(
                qs.aggregate(avg=Coalesce(Avg("attempts"), Value(0, output_field=FloatField())))["avg"]
            ),
        }
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size else 1

        payload = {
            "results": PendingCallSerializer(res.items, many=True).data,
            "total_items": total_items,
            "summary": summary,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "items_on_page": len(res.items),
        }
        return Response(payload, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------ #
    @track_http("PendingCallViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = {"clinic_id": str(request.user.clinic_id)}
        pc = notification_billing_query_bus.dispatch(
            GetPendingCallQuery(filtros=filtros, id=str(pk))
        )
        return Response(PendingCallSerializer(pc).data)

    # ------------------------------------------------------------------ #
    @track_http("PendingCallViewSet_mark_done")
    @action(methods=["post"], detail=True, url_path="mark-done")
    def mark_done(self, request, pk=None):
        """
        Marca a pendência como concluída ou falhada.

        Body:
        ```
        {
          "success": true,
          "notes": "Paciente retornou ligação"
        }
        ```
        """
        success = bool(request.data.get("success", True))
        notes = request.data.get("notes")

        notification_billing_command_bus.dispatch(
            SetPendingCallDoneCommand(
                call_id=str(pk),
                success=success,
                notes=notes,
                user_id=str(request.user.id),
            )
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class BillingSettingsViewSet(PaginationFilterMixin, viewsets.ViewSet):
    """
    Visualiza e atualiza as configurações de cobrança por clínica.
    """
    permission_classes = [IsClinicUser]

    @track_http("BillingSettingsViewSet_list")
    def list(self, request):
        # para admins, listar todas; para clinic_user, só a própria
        filtros = {}
        if getattr(request.user, "role", None) == "clinic":
            filtros["clinic_id"] = str(request.user.clinic_id)
        page, page_size = self._pagination(request)
        q = ListBillingSettingsQuery(filtros=filtros, page=page, page_size=page_size)
        res = core_query_bus.dispatch(q)
        total = res.total
        total_pages = math.ceil(total / page_size) if page_size else 1
        data = BillingSettingsSerializer(res.items, many=True).data
        return Response({
            "results": data,
            "total_items": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "items_on_page": len(res.items),
        }, status=status.HTTP_200_OK)

    @track_http("BillingSettingsViewSet_retrieve")
    def retrieve(self, request, pk=None):
        filtros = {}
        if getattr(request.user, "role", None) == "clinic":
            filtros["clinic_id"] = str(request.user.clinic_id)
        setting = core_query_bus.dispatch(
            GetBillingSettingsQuery(filtros=filtros, clinic_id=str(pk))
        )
        return Response(BillingSettingsSerializer(setting).data)

    @track_http("BillingSettingsViewSet_update")
    def update(self, request, pk=None):
        payload = request.data
        cmd = UpdateBillingSettingsCommand(
            clinic_id=str(pk),
            min_days_overdue=int(payload.get("min_days_overdue", 90))
        )
        updated = core_command_bus.dispatch(cmd)
        return Response(
            BillingSettingsSerializer(updated).data,
            status=status.HTTP_200_OK
        )
        

class PaymentMethodViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        res  = core_query_bus.dispatch(ListPaymentMethodsQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        payment_methods_serializados = PaymentMethodSerializer(res.items, many=True).data

        payload = {
            "results": payment_methods_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)
    

    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        pm = core_query_bus.dispatch(GetPaymentMethodQuery(filtros=filtros, payment_method_id=str(pk)))
        return Response(PaymentMethodSerializer(pm).data)


class FlowStepConfigViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        res = notification_billing_query_bus.dispatch(ListFlowStepConfigsQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        flow_step_config_serializados = FlowStepConfigSerializer(res.items, many=True).data

        payload = {
            "results": flow_step_config_serializados,     
            "total_items": total_items,            
            "page": page,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        filtros = self._filters(request)
        cfg = notification_billing_query_bus.dispatch(GetFlowStepConfigQuery(filtros=filtros, payment_method_id=str(pk)))
        return Response(FlowStepConfigSerializer(cfg).data)



class CollectionCaseViewSet(PaginationFilterMixin, viewsets.ViewSet):
    permission_classes = [IsClinicUser]

    def list(self, request):
        filtros = {"clinic_id": str(request.user.clinic_id), **self._filters(request)}
        page, page_size = self._pagination(request)
        res = cordial_billing_query_bus.dispatch(ListCollectionCasesQuery(filtros=filtros, page=page, page_size=page_size))
        
        total_items = res.total
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        collection_cases_serializados = CollectionCaseSerializer(res.items, many=True).data

        payload = {
            "results": collection_cases_serializados,     
            "total_items": total_items,            
            "page": page_size,                          # página atual (extraído de self._pagination)
            "page_size": page_size,                # quantidade de itens por página
            "total_pages": total_pages,            # número total de páginas
            "items_on_page": len(res.items),
        }

        return Response(payload, status=status.HTTP_200_OK)
    

    def retrieve(self, request, pk=None):
        case = cordial_billing_query_bus.dispatch(
            GetCollectionCaseQuery(collection_case_id=str(pk), filtros={"clinic_id": str(request.user.clinic_id)})
        )
        return Response(CollectionCaseSerializer(case).data) 
    
    @action(detail=True, methods=["post"])  # POST /collection-case/{id}/create_deal
    def create_deal(self, request, pk=None):
        result = cordial_billing_command_bus.dispatch(
            CreatePipedriveDealCommand(collection_case_id=str(pk))
        )
        return Response(result, status=status.HTTP_201_CREATED)

class RegistrationRequestViewSet(PaginationFilterMixin, viewsets.ViewSet):
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'create':
            self.permission_classes = [permissions.AllowAny]
        else:
            self.permission_classes = [IsAdminUser,]
        return super().get_permissions()

    @track_http("RegistrationRequestViewSet_create")
    def create(self, request):
        dto = CreateRegistrationRequestDTO(**request.data)
        cmd = CreateRegistrationRequestCommand(payload=dto)
        _result = core_command_bus.dispatch(cmd)
        return Response(
            {"message": "Solicitação de registro enviada com sucesso. Aguarde a aprovação do administrador."},
            status=status.HTTP_201_CREATED
        )

    @track_http("RegistrationRequestViewSet_list")
    def list(self, request):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)
        query = ListRegistrationRequestsQuery(filtros=filtros, page=page, page_size=page_size)
        paged_result = core_query_bus.dispatch(query)
        serializer = RegistrationRequestSerializer(paged_result.items, many=True)
        return Response({
            "results": serializer.data,
            "total_items": paged_result.total,
            "page": paged_result.page,
            "page_size": paged_result.page_size,
            "total_pages": paged_result.total_pages,
        })
        
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        # 1. carrega a registration_request
        rr = core_query_bus.dispatch(GetRegistrationRequestQuery(filtros={} ,request_id=pk))

        # 2. descriptografa a senha
        raw_password = FERNET.decrypt(rr.password_enc.encode()).decode()

        # 3. manda tudo para o Command
        cmd = ApproveRegistrationRequestCommand(
            request_id=pk,
            raw_password=raw_password,
        )
        core_command_bus.dispatch(cmd)
        return Response(
            {"message": "Registro aprovado e processo de configuração da clínica iniciado."},
            status=status.HTTP_200_OK,
        )

    @track_http("RegistrationRequestViewSet_reject")
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        cmd = RejectRegistrationRequestCommand(request_id=pk)
        core_command_bus.dispatch(cmd)
        return Response({"message": "Solicitação de registro rejeitada."}, status=status.HTTP_200_OK)
