from rest_framework import serializers

from plugins.django_interface.serializers.core_serializers import (
    AddressSerializer,
    ClinicDataSerializer,
    ClinicPhoneSerializer,
    ClinicSerializer,
    CollectionCaseSerializer,
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


# ───────────────────────────────────────────────
# Paginação genérica
# ───────────────────────────────────────────────
class PaginatedResponseSerializer(serializers.Serializer):
    results = serializers.ListField(
        child=serializers.DictField(), help_text="Lista de itens paginados"
    )
    total = serializers.IntegerField(help_text="Total de itens disponíveis")


# ───────────────────────────────────────────────
# Tipos específicos
# ───────────────────────────────────────────────
class PaginatedPatientResponseSerializer(PaginatedResponseSerializer):
    results = PatientSerializer(many=True)


class PaginatedAddressResponseSerializer(PaginatedResponseSerializer):
    results = AddressSerializer(many=True)


class PaginatedClinicResponseSerializer(PaginatedResponseSerializer):
    results = ClinicSerializer(many=True)


class PaginatedClinicDataResponseSerializer(PaginatedResponseSerializer):
    results = ClinicDataSerializer(many=True)


class PaginatedClinicPhoneResponseSerializer(PaginatedResponseSerializer):
    results = ClinicPhoneSerializer(many=True)


class PaginatedCoveredClinicResponseSerializer(PaginatedResponseSerializer):
    results = CoveredClinicSerializer(many=True)


class PaginatedPatientPhoneResponseSerializer(PaginatedResponseSerializer):
    results = PatientPhoneSerializer(many=True)


class PaginatedContractResponseSerializer(PaginatedResponseSerializer):
    results = ContractSerializer(many=True)


class PaginatedInstallmentResponseSerializer(PaginatedResponseSerializer):
    results = InstallmentSerializer(many=True)


class PaginatedContactScheduleResponseSerializer(PaginatedResponseSerializer):
    results = ContactScheduleSerializer(many=True)


class PaginatedContactHistoryResponseSerializer(PaginatedResponseSerializer):
    results = ContactHistorySerializer(many=True)


class PaginatedUserClinicResponseSerializer(PaginatedResponseSerializer):
    results = UserClinicSerializer(many=True)


class PaginatedMessageResponseSerializer(PaginatedResponseSerializer):
    results = MessageSerializer(many=True)


class PaginatedUserResponseSerializer(PaginatedResponseSerializer):
    results = UserSerializer(many=True)


# ───────────────────────────────────────────────
# DTO / Request Serializers
# ───────────────────────────────────────────────
class UpdatePatientDTOSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    cpf = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_null=True)


class PatientRegisterSerializer(serializers.Serializer):
    initial_due_date = serializers.DateField()
    final_due_date = serializers.DateField()
    user_id = serializers.UUIDField(required=False, allow_null=True)


class AddressCreateSerializer(serializers.Serializer):
    street = serializers.CharField()
    number = serializers.CharField()
    complement = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    neighborhood = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField()
    state = serializers.CharField()
    zip_code = serializers.CharField()


class AddressUpdateSerializer(AddressCreateSerializer):
    """Todas as fields opcionais (view usa partial=True)."""
    pass


class ClinicCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    cnpj = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ClinicUpdateSerializer(ClinicCreateSerializer):
    pass


class ClinicDataCreateSerializer(serializers.Serializer):
    clinic_id = serializers.UUIDField()
    address_id = serializers.UUIDField(required=False, allow_null=True)
    corporate_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    acronym = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    active = serializers.BooleanField(default=False)
    franchise = serializers.BooleanField(default=False)
    timezone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    first_billing_date = serializers.DateField(required=False, allow_null=True)


class ClinicDataUpdateSerializer(ClinicDataCreateSerializer):
    pass


class ClinicPhoneCreateSerializer(serializers.Serializer):
    clinic_id = serializers.UUIDField()
    phone_number = serializers.CharField()
    phone_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ClinicPhoneUpdateSerializer(ClinicPhoneCreateSerializer):
    pass


class CoveredClinicCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField()


class PatientPhoneCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    phone_number = serializers.CharField()
    phone_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PatientPhoneUpdateSerializer(PatientPhoneCreateSerializer):
    pass


class ContractFilterSerializer(serializers.Serializer):
    clinic_id = serializers.UUIDField(required=False)
    patient_id = serializers.UUIDField(required=False)
    status = serializers.CharField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class InstallmentFilterSerializer(serializers.Serializer):
    contract_id = serializers.UUIDField(required=False)
    installment_status = serializers.CharField(required=False)
    received = serializers.BooleanField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class ContactSchedulePayloadSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    contract_id = serializers.UUIDField(required=False, allow_null=True)
    clinic_id = serializers.UUIDField()
    current_step = serializers.IntegerField()
    channel = serializers.CharField()
    scheduled_date = serializers.DateTimeField()
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    installment_id = serializers.UUIDField(required=False, allow_null=True)


class ScheduleFirstContactRequestSerializer(serializers.Serializer):
    contract_id = serializers.UUIDField()
    installment_id = serializers.UUIDField(required=False, allow_null=True)


class GenericMessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class MessageCreateSerializer(serializers.Serializer):
    type = serializers.CharField()
    content = serializers.CharField()
    step = serializers.IntegerField()
    clinic_id = serializers.UUIDField(required=False, allow_null=True)
    is_default = serializers.BooleanField(default=False)


class MessageUpdateSerializer(MessageCreateSerializer):
    pass


class UserCreateRequestDTOSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=["admin", "clinic"])
    clinic_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class UserUpdateDTOSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["admin", "clinic"], required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    name = serializers.CharField(required=False)
    clinic_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)


CoreUserSerializer = UserSerializer


class PaginatedCollectionCaseResponseSerializer(PaginatedResponseSerializer):
    results = CollectionCaseSerializer(many=True)