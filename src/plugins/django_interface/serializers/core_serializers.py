from rest_framework import serializers


# ───────────────────────────────────────────────
# Endereços
# ───────────────────────────────────────────────
class AddressSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    street = serializers.CharField()
    number = serializers.CharField()
    complement = serializers.CharField(allow_blank=True, allow_null=True)
    neighborhood = serializers.CharField(allow_blank=True, allow_null=True)
    city = serializers.CharField()
    state = serializers.CharField()
    zip_code = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Usuários e vínculo User ↔ Clinic
# ───────────────────────────────────────────────
class UserClinicSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(source="user")
    clinic_id = serializers.UUIDField(source="clinic")
    linked_at = serializers.DateTimeField()


class UserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    clinic_name = serializers.CharField(allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField()
    role = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Clínicas e telefones
# ───────────────────────────────────────────────
class ClinicSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    oralsin_clinic_id = serializers.IntegerField()
    name = serializers.CharField()
    cnpj = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ClinicDataSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    clinic_id = serializers.UUIDField(source="clinic")
    corporate_name = serializers.CharField(allow_blank=True, allow_null=True)
    acronym = serializers.CharField(allow_blank=True, allow_null=True)
    address = AddressSerializer(allow_null=True)
    active = serializers.BooleanField()
    franchise = serializers.BooleanField()
    timezone = serializers.CharField(allow_blank=True, allow_null=True)
    first_billing_date = serializers.DateField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ClinicPhoneSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    clinic_id = serializers.UUIDField(source="clinic")
    phone_number = serializers.CharField()
    phone_type = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Covered Clinic
# ───────────────────────────────────────────────
class CoveredClinicSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    clinic_id = serializers.UUIDField(source="clinic")
    oralsin_clinic_id = serializers.IntegerField()
    name = serializers.CharField()
    cnpj = serializers.CharField(allow_blank=True, allow_null=True)
    corporate_name = serializers.CharField(allow_blank=True, allow_null=True)
    acronym = serializers.CharField(allow_blank=True, allow_null=True)
    active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Pacientes
# ───────────────────────────────────────────────
class PatientPhoneSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    patient_id = serializers.UUIDField(source="patient")
    phone_number = serializers.CharField()
    phone_type = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class PatientSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    oralsin_patient_id = serializers.IntegerField(allow_null=True)
    clinic_id = serializers.UUIDField(source="clinic")
    name = serializers.CharField()
    cpf = serializers.CharField(allow_blank=True, allow_null=True)
    address = AddressSerializer(allow_null=True)
    email = serializers.EmailField(allow_blank=True, allow_null=True)
    is_notification_enabled = serializers.BooleanField()
    phones = PatientPhoneSerializer(many=True, source="phones", default=[])
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Contratos e parcelas
# ───────────────────────────────────────────────
class PaymentMethodSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    oralsin_payment_method_id = serializers.IntegerField()
    name = serializers.CharField()


class ContractSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    oralsin_contract_id = serializers.IntegerField(allow_null=True)
    patient_id = serializers.UUIDField(source="patient")
    clinic_id = serializers.UUIDField(source="clinic")
    status = serializers.CharField()
    contract_version = serializers.CharField(allow_blank=True, allow_null=True)
    remaining_installments = serializers.IntegerField()
    overdue_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    valor_contrato_final = serializers.DecimalField(max_digits=14, decimal_places=2)
    realizar_cobranca = serializers.BooleanField()
    first_billing_date = serializers.DateField(allow_null=True)
    negotiation_notes = serializers.CharField(allow_blank=True, allow_null=True)
    payment_method = PaymentMethodSerializer(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class InstallmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    contract_id = serializers.UUIDField(source="contract")
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    installment_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    received = serializers.BooleanField()
    installment_status = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Fluxo de cobrança
# ───────────────────────────────────────────────
class FlowStepConfigSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    step_number = serializers.IntegerField()
    channels = serializers.ListField(child=serializers.CharField())
    active = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True, allow_null=True)
    cooldown_days = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class MessageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    type = serializers.CharField()
    content = serializers.CharField()
    step = serializers.IntegerField()
    clinic_id = serializers.UUIDField(allow_null=True, source="clinic")
    is_default = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ContactScheduleSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    patient_id = serializers.UUIDField(source="patient")
    contract_id = serializers.UUIDField(source="contract", allow_null=True)
    clinic_id = serializers.UUIDField(source="clinic")
    notification_trigger = serializers.CharField()
    advance_flow = serializers.BooleanField()
    current_step = serializers.IntegerField()
    channel = serializers.CharField()
    scheduled_date = serializers.DateTimeField()
    status = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ContactHistorySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    patient_id = serializers.UUIDField(source="patient")
    contract_id = serializers.UUIDField(source="contract", allow_null=True)
    clinic_id = serializers.UUIDField(source="clinic")
    notification_trigger = serializers.CharField()
    advance_flow = serializers.BooleanField()
    contact_type = serializers.CharField()
    sent_at = serializers.DateTimeField(allow_null=True)
    duration_ms = serializers.IntegerField(allow_null=True)
    feedback_status = serializers.CharField(allow_blank=True, allow_null=True)
    observation = serializers.CharField(allow_blank=True, allow_null=True)
    message_id = serializers.UUIDField(source="message", allow_null=True)
    schedule_id = serializers.UUIDField(source="schedule", allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
