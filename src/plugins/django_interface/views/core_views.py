from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from oralsin_core.adapters.config.composition_root import container as core_container
from oralsin_core.adapters.observability.decorators import track_http

# ───────────────────────────────────────────────
# Commands & DTOs
# ───────────────────────────────────────────────
from oralsin_core.core.application.commands.address_commands import (
    CreateAddressCommand,
    DeleteAddressCommand,
    UpdateAddressCommand,
)
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
from oralsin_core.core.application.commands.covered_clinic_commands import RegisterCoveredClinicCommand
from oralsin_core.core.application.commands.patient_commands import (
    RegisterPatientsCommand,
    UpdatePatientCommand,
)
from oralsin_core.core.application.commands.patient_phone_commands import (
    CreatePatientPhoneCommand,
    DeletePatientPhoneCommand,
    UpdatePatientPhoneCommand,
)
from oralsin_core.core.application.commands.user_commands import (
    CreateUserCommand,
    DeleteUserCommand,
    UpdateUserCommand,
)
from oralsin_core.core.application.cqrs import CommandBusImpl, QueryBusImpl
from oralsin_core.core.application.dtos.address_dto import AddressDTO
from oralsin_core.core.application.dtos.clinic_data_dto import ClinicDataDTO
from oralsin_core.core.application.dtos.clinic_dto import ClinicDTO
from oralsin_core.core.application.dtos.clinic_phone_dto import ClinicPhoneDTO
from oralsin_core.core.application.dtos.covered_clinic_dto import CoveredClinicCreateDTO
from oralsin_core.core.application.dtos.patient_dto import (
    RegisterPatientsDTO,
    UpdatePatientDTO,
)
from oralsin_core.core.application.dtos.patient_phone_dto import PatientPhoneDTO
from oralsin_core.core.application.dtos.user_dto import CreateUserDTO, UpdateUserDTO
from oralsin_core.core.application.queries.address_queries import GetAddressQuery, ListAddressesQuery
from oralsin_core.core.application.queries.clinic_data_queries import GetClinicDataQuery, ListClinicDataQuery
from oralsin_core.core.application.queries.clinic_phone_queries import GetClinicPhoneQuery, ListClinicPhonesQuery
from oralsin_core.core.application.queries.clinic_queries import GetClinicQuery, ListClinicsQuery
from oralsin_core.core.application.queries.contract_queries import GetContractQuery, ListContractsQuery
from oralsin_core.core.application.queries.covered_clinic_queries import GetCoveredClinicQuery, ListCoveredClinicsQuery
from oralsin_core.core.application.queries.installment_queries import GetInstallmentQuery, ListInstallmentsQuery
from oralsin_core.core.application.queries.patient_phone_queries import GetPatientPhoneQuery, ListPatientPhonesQuery
from oralsin_core.core.application.queries.patient_queries import GetPatientQuery, ListPatientsQuery
from oralsin_core.core.application.queries.user_clinic_queries import GetUserClinicQuery, ListUserClinicsQuery
from oralsin_core.core.application.queries.user_queries import GetUserQuery, ListUsersQuery
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from notification_billing.adapters.config.composition_root import container as billing_container
from notification_billing.core.application.commands.contact_schedule_commands import (
    CreateContactScheduleCommand,
    DeleteContactScheduleCommand,
    UpdateContactScheduleCommand,
)
from notification_billing.core.application.commands.message_commands import (
    CreateMessageCommand,
    DeleteMessageCommand,
    UpdateMessageCommand,
)
from notification_billing.core.application.dtos.message_dto import MessageDTO
from notification_billing.core.application.dtos.schedule_dto import ContactScheduleDTO
from notification_billing.core.application.queries.contact_history_queries import GetContactHistoryQuery, ListContactHistoryQuery
from notification_billing.core.application.queries.contact_queries import ListDueContactsQuery
from notification_billing.core.application.queries.contact_schedule_queries import GetContactScheduleQuery
from notification_billing.core.application.queries.message_queries import GetMessageQuery, ListMessagesQuery
from plugins.django_interface.permissions import IsAdminUser, IsClinicUser

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

# Bus instances
core_command_bus: CommandBusImpl = core_container.command_bus()
core_query_bus: QueryBusImpl = core_container.query_bus()
billing_command_bus: CommandBusImpl = billing_container.command_bus()
billing_query_bus: QueryBusImpl = billing_container.query_bus()

LIST_TTL     = 5 * 60    # 5 minutos
RETRIEVE_TTL = 10 * 60   # 10 minutos

# ────────────────────────────────
# Core Domain ViewSets (Oralsin)
# ────────────────────────────────

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('PatientViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('PatientViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('PatientViewSet_update'), name='update')
@method_decorator(track_http('PatientViewSet_sync'), name='sync')
class PatientViewSet(viewsets.ViewSet):
    """CRUD para pacientes."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        q = ListPatientsQuery(
            filtros=request.query_params.dict(),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': PatientSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        pat = core_query_bus.dispatch(GetPatientQuery(id=pk))
        return Response(PatientSerializer(pat).data)

    def update(self, request, pk=None):
        dto = UpdatePatientDTO(**request.data)
        pat = core_command_bus.dispatch(UpdatePatientCommand(id=pk, payload=dto))
        return Response(PatientSerializer(pat).data)

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        dto = RegisterPatientsDTO(
            user_id=str(request.user.id),
            initial_due_date=request.data.get("initial_due_date"),
            final_due_date=request.data.get("final_due_date"),
        )
        res = core_command_bus.dispatch(RegisterPatientsCommand(payload=dto))
        return Response({'message': 'Sync iniciado', 'result': res})

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('AddressViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('AddressViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('AddressViewSet_create'), name='create')
@method_decorator(track_http('AddressViewSet_update'), name='update')
@method_decorator(track_http('AddressViewSet_destroy'), name='destroy')
class AddressViewSet(viewsets.ViewSet):
    """CRUD para endereços."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        q = ListAddressesQuery(
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': AddressSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        addr = core_query_bus.dispatch(GetAddressQuery(id=pk))
        return Response(AddressSerializer(addr).data)

    def create(self, request):
        dto = AddressDTO(**request.data)
        addr = core_command_bus.dispatch(CreateAddressCommand(payload=dto))
        return Response(AddressSerializer(addr).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        dto = AddressDTO(**request.data)
        addr = core_command_bus.dispatch(UpdateAddressCommand(id=pk, payload=dto))
        return Response(AddressSerializer(addr).data)

    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeleteAddressCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('ClinicViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('ClinicViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('ClinicViewSet_create'), name='create')
@method_decorator(track_http('ClinicViewSet_update'), name='update')
@method_decorator(track_http('ClinicViewSet_destroy'), name='destroy')
class ClinicViewSet(viewsets.ViewSet):
    """CRUD para clínicas principais."""
    permission_classes = [IsAdminUser]
    def list(self, request):
        q = ListClinicsQuery(
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': ClinicSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        c = core_query_bus.dispatch(GetClinicQuery(id=pk))
        return Response(ClinicSerializer(c).data)

    def create(self, request):
        dto = ClinicDTO(**request.data)
        c = core_command_bus.dispatch(CreateClinicCommand(payload=dto))
        return Response(ClinicSerializer(c).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        dto = ClinicDTO(**request.data)
        c = core_command_bus.dispatch(UpdateClinicCommand(id=pk, payload=dto))
        return Response(ClinicSerializer(c).data)

    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeleteClinicCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('ClinicDataViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('ClinicDataViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('ClinicDataViewSet_create'), name='create')
@method_decorator(track_http('ClinicDataViewSet_update'), name='update')
class ClinicDataViewSet(viewsets.ViewSet):
    """CRUD para dados complementares de clínica."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        filtros = {}
        if getattr(request.user, "role", None) == "clinic":
            filtros["clinic_id"] = request.user.clinic_id
        q = ListClinicDataQuery(
            filtros=filtros,
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': ClinicDataSerializer(res.items, many=True).data, 'total': res.total})


    def retrieve(self, request, pk=None):
        cd = core_query_bus.dispatch(GetClinicDataQuery(id=pk))
        return Response(ClinicDataSerializer(cd).data)

    def create(self, request):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        dto = ClinicDataDTO(**payload)
        cd = core_command_bus.dispatch(CreateClinicDataCommand(payload=dto))
        return Response(ClinicDataSerializer(cd).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        dto = ClinicDataDTO(**payload)
        cd = core_command_bus.dispatch(UpdateClinicDataCommand(id=pk, payload=dto))
        return Response(ClinicDataSerializer(cd).data)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('ClinicPhoneViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('ClinicPhoneViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('ClinicPhoneViewSet_create'), name='create')
@method_decorator(track_http('ClinicPhoneViewSet_update'), name='update')
@method_decorator(track_http('ClinicPhoneViewSet_destroy'), name='destroy')
class ClinicPhoneViewSet(viewsets.ViewSet):
    """CRUD para telefones de clínica."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        filtros = {}
        if getattr(request.user, "role", None) == "clinic":
            filtros["clinic_id"] = request.user.clinic_id
        q = ListClinicPhonesQuery(
            filtros=filtros,
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': ClinicPhoneSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        cp = core_query_bus.dispatch(GetClinicPhoneQuery(id=pk))
        return Response(ClinicPhoneSerializer(cp).data)

    def create(self, request):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        dto = ClinicPhoneDTO(**payload)
        cp = core_command_bus.dispatch(CreateClinicPhoneCommand(payload=dto))
        return Response(ClinicPhoneSerializer(cp).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        payload = dict(request.data)
        if getattr(request.user, "role", None) == "clinic":
            payload["clinic_id"] = str(request.user.clinic_id)
        dto = ClinicPhoneDTO(**payload)
        cp = core_command_bus.dispatch(UpdateClinicPhoneCommand(id=pk, payload=dto))
        return Response(ClinicPhoneSerializer(cp).data)

    def destroy(self, request, pk=None):
        cmd = DeleteClinicPhoneCommand(id=pk)
        core_command_bus.dispatch(cmd)
        return Response(status=status.HTTP_204_NO_CONTENT)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('CoveredClinicViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('CoveredClinicViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('CoveredClinicViewSet_create'), name='create')
class CoveredClinicViewSet(viewsets.ViewSet):
    """CRUD para clínicas cobertas."""
    permission_classes = [IsAdminUser]
    def list(self, request):
        q = ListCoveredClinicsQuery(
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': CoveredClinicSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        cov = core_query_bus.dispatch(GetCoveredClinicQuery(id=pk))
        return Response(CoveredClinicSerializer(cov).data)

    def create(self, request):
        dto = CoveredClinicCreateDTO(**request.data)
        cov = core_command_bus.dispatch(RegisterCoveredClinicCommand(payload=dto))
        return Response(CoveredClinicSerializer(cov).data, status=status.HTTP_201_CREATED)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('PatientPhoneViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('PatientPhoneViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('PatientPhoneViewSet_create'), name='create')
@method_decorator(track_http('PatientPhoneViewSet_update'), name='update')
@method_decorator(track_http('PatientPhoneViewSet_destroy'), name='destroy')
class PatientPhoneViewSet(viewsets.ViewSet):
    """CRUD para telefones de paciente."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        q = ListPatientPhonesQuery(
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': PatientPhoneSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        pp = core_query_bus.dispatch(GetPatientPhoneQuery(id=pk))
        return Response(PatientPhoneSerializer(pp).data)

    def create(self, request):
        dto = PatientPhoneDTO(**request.data)
        pp = core_command_bus.dispatch(CreatePatientPhoneCommand(payload=dto))
        return Response(PatientPhoneSerializer(pp).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        dto = PatientPhoneDTO(**request.data)
        pp = core_command_bus.dispatch(UpdatePatientPhoneCommand(id=pk, payload=dto))
        return Response(PatientPhoneSerializer(pp).data)

    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeletePatientPhoneCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('ContractViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('ContractViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('ContractViewSet_installments'), name='installments')
class ContractViewSet(viewsets.ViewSet):
    """CRUD para contratos."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        q = ListContractsQuery(
            filtros=request.query_params.dict(),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': ContractSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        ctr = core_query_bus.dispatch(GetContractQuery(id=pk))
        return Response(ContractSerializer(ctr).data)

    @action(detail=True, methods=['get'])
    def installments(self, request, pk=None):
        q = ListInstallmentsQuery(
            filtros={'contract_id': pk},
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': InstallmentSerializer(res.items, many=True).data, 'total': res.total})

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('InstallmentViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('InstallmentViewSet_retrieve'), name='retrieve')
class InstallmentViewSet(viewsets.ViewSet):
    """CRUD para parcelas."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        q = ListInstallmentsQuery(
            filtros=request.query_params.dict(),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': InstallmentSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        inst = core_query_bus.dispatch(GetInstallmentQuery(id=pk))
        return Response(InstallmentSerializer(inst).data)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('UserClinicViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('UserClinicViewSet_retrieve'), name='retrieve')
class UserClinicViewSet(viewsets.ViewSet):
    """Leitura de vínculo Usuário↔Clínica."""
    permission_classes = [IsAdminUser]
    def list(self, request):
        q = ListUserClinicsQuery(
            filtros=request.query_params.dict(),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': UserClinicSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        uc = core_query_bus.dispatch(GetUserClinicQuery(id=pk))
        return Response(UserClinicSerializer(uc).data)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('UserViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('UserViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('UserViewSet_create'), name='create')
@method_decorator(track_http('UserViewSet_update'), name='update')
@method_decorator(track_http('UserViewSet_destroy'), name='destroy')
class UserViewSet(viewsets.ViewSet):
    """CRUD para usuários."""
    permission_classes = [IsAdminUser]
    def list(self, request):
        q = ListUsersQuery(
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        return Response({'results': UserSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        user = core_query_bus.dispatch(GetUserQuery(id=pk))
        return Response(UserSerializer(user).data)

    def create(self, request):
        dto = CreateUserDTO(**request.data)
        user = core_command_bus.dispatch(CreateUserCommand(payload=dto))
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        dto = UpdateUserDTO(**request.data)
        user = core_command_bus.dispatch(UpdateUserCommand(id=pk, payload=dto))
        return Response(UserSerializer(user).data)

    def destroy(self, request, pk=None):
        core_command_bus.dispatch(DeleteUserCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

# ────────────────────────────────
# Billing Domain ViewSets (Notificações)
# ────────────────────────────────

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('ContactScheduleViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('ContactScheduleViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('ContactScheduleViewSet_create'), name='create')
@method_decorator(track_http('ContactScheduleViewSet_update'), name='update')
@method_decorator(track_http('ContactScheduleViewSet_destroy'), name='destroy')
class ContactScheduleViewSet(viewsets.ViewSet):
    """CRUD para agendamento de contatos."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        q = ListDueContactsQuery(
            filtros={'clinic_id': request.user.clinic_id},
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = billing_query_bus.dispatch(q)
        return Response({'results': ContactScheduleSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        cs = billing_query_bus.dispatch(GetContactScheduleQuery(id=pk))
        return Response(ContactScheduleSerializer(cs).data)

    def create(self, request):
        dto = ContactScheduleDTO(**request.data)
        cs = billing_command_bus.dispatch(CreateContactScheduleCommand(payload=dto))
        return Response(ContactScheduleSerializer(cs).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        dto = ContactScheduleDTO(**request.data)
        cs = billing_command_bus.dispatch(UpdateContactScheduleCommand(id=pk, payload=dto))
        return Response(ContactScheduleSerializer(cs).data)

    def destroy(self, request, pk=None):
        billing_command_bus.dispatch(DeleteContactScheduleCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('ContactHistoryViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('ContactHistoryViewSet_retrieve'), name='retrieve')
class ContactHistoryViewSet(viewsets.ViewSet):
    """CRUD para histórico de contatos."""
    permission_classes = [IsClinicUser]
    def list(self, request):
        q = ListContactHistoryQuery(
            filtros=request.query_params.dict(),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = billing_query_bus.dispatch(q)
        return Response({'results': ContactHistorySerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        ch = billing_query_bus.dispatch(GetContactHistoryQuery(id=pk))
        return Response(ContactHistorySerializer(ch).data)

@method_decorator(cache_page(LIST_TTL), name='list')
@method_decorator(track_http('MessageViewSet_list'), name='list')
@method_decorator(cache_page(RETRIEVE_TTL), name='retrieve')
@method_decorator(track_http('MessageViewSet_retrieve'), name='retrieve')
@method_decorator(track_http('MessageViewSet_create'), name='create')
@method_decorator(track_http('MessageViewSet_update'), name='update')
@method_decorator(track_http('MessageViewSet_destroy'), name='destroy')
class MessageViewSet(viewsets.ViewSet):
    """CRUD para templates de mensagem."""
    permission_classes = [IsAdminUser]
    def list(self, request):
        q = ListMessagesQuery(
            filtros=request.query_params.dict(),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = billing_query_bus.dispatch(q)
        return Response({'results': MessageSerializer(res.items, many=True).data, 'total': res.total})

    def retrieve(self, request, pk=None):
        m = billing_query_bus.dispatch(GetMessageQuery(id=pk))
        return Response(MessageSerializer(m).data)

    def create(self, request):
        dto = MessageDTO(**request.data)
        m = billing_command_bus.dispatch(CreateMessageCommand(payload=dto))
        return Response(MessageSerializer(m).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        dto = MessageDTO(**request.data)
        m = billing_command_bus.dispatch(UpdateMessageCommand(id=pk, payload=dto))
        return Response(MessageSerializer(m).data)

    def destroy(self, request, pk=None):
        billing_command_bus.dispatch(DeleteMessageCommand(id=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
