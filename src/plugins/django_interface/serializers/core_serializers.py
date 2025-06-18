# =========================================================
# Serializers compatíveis com as *entities* (e não com os
# modelos Django) — não usam relações “aninhadas” inexistentes
# e evitam `source=` redundante.
# =========================================================
from rest_framework import serializers

from plugins.django_interface.models import CollectionCase


# ───────────────────────────────────────────────
# Endereços
# ───────────────────────────────────────────────
class AddressSerializer(serializers.Serializer):
    id          = serializers.UUIDField()
    street      = serializers.CharField()
    number      = serializers.CharField()
    complement  = serializers.CharField(allow_blank=True, allow_null=True)
    neighborhood = serializers.CharField(allow_blank=True, allow_null=True)
    city        = serializers.CharField()
    state       = serializers.CharField()
    zip_code    = serializers.CharField()
    created_at  = serializers.DateTimeField()
    updated_at  = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Usuários  &  User ⇄ Clinic
# ───────────────────────────────────────────────
class UserClinicSerializer(serializers.Serializer):
    user_id   = serializers.UUIDField()
    clinic_id = serializers.UUIDField()
    linked_at = serializers.DateTimeField()


class UserSerializer(serializers.Serializer):
    id          = serializers.UUIDField()
    email       = serializers.EmailField()
    name        = serializers.CharField()
    clinic_name = serializers.CharField(allow_blank=True, allow_null=True)
    is_active   = serializers.BooleanField()
    role        = serializers.CharField()
    created_at  = serializers.DateTimeField()
    updated_at  = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Clínicas  &  Telefones
# ───────────────────────────────────────────────
class ClinicSerializer(serializers.Serializer):
    id                = serializers.UUIDField()
    oralsin_clinic_id = serializers.IntegerField()
    name              = serializers.CharField()
    cnpj              = serializers.CharField(allow_blank=True, allow_null=True)
    created_at        = serializers.DateTimeField()
    updated_at        = serializers.DateTimeField()


class ClinicDataSerializer(serializers.Serializer):
    id                 = serializers.UUIDField()
    clinic_id          = serializers.UUIDField()
    corporate_name     = serializers.CharField(allow_blank=True, allow_null=True)
    acronym            = serializers.CharField(allow_blank=True, allow_null=True)
    address            = AddressSerializer(allow_null=True)
    active             = serializers.BooleanField()
    franchise          = serializers.BooleanField()
    timezone           = serializers.CharField(allow_blank=True, allow_null=True)
    first_billing_date = serializers.DateField(allow_null=True)
    created_at         = serializers.DateTimeField()
    updated_at         = serializers.DateTimeField()


class ClinicPhoneSerializer(serializers.Serializer):
    id          = serializers.UUIDField()
    clinic_id   = serializers.UUIDField()
    phone_number = serializers.CharField()
    phone_type   = serializers.CharField(allow_blank=True, allow_null=True)
    created_at   = serializers.DateTimeField()
    updated_at   = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Covered Clinic
# ───────────────────────────────────────────────
class CoveredClinicSerializer(serializers.Serializer):
    id                = serializers.UUIDField()
    clinic_id         = serializers.UUIDField()
    oralsin_clinic_id = serializers.IntegerField()
    name              = serializers.CharField()
    cnpj              = serializers.CharField(allow_blank=True, allow_null=True)
    corporate_name    = serializers.CharField(allow_blank=True, allow_null=True)
    acronym           = serializers.CharField(allow_blank=True, allow_null=True)
    active            = serializers.BooleanField()
    created_at        = serializers.DateTimeField()
    updated_at        = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Pacientes
# ───────────────────────────────────────────────
class PatientPhoneSerializer(serializers.Serializer):
    id           = serializers.UUIDField()
    patient_id   = serializers.UUIDField()
    phone_number = serializers.CharField()
    phone_type   = serializers.CharField(allow_blank=True, allow_null=True)
    created_at   = serializers.DateTimeField()
    updated_at   = serializers.DateTimeField()


class PatientSerializer(serializers.Serializer):
    id                       = serializers.UUIDField()
    oralsin_patient_id       = serializers.IntegerField(allow_null=True)
    clinic_id                = serializers.UUIDField()
    name                     = serializers.CharField()
    contact_name             = serializers.CharField(allow_blank=True, allow_null=True)
    cpf                      = serializers.CharField(allow_blank=True, allow_null=True)
    address                  = AddressSerializer(allow_null=True)
    email                    = serializers.EmailField(allow_blank=True, allow_null=True)
    is_notification_enabled  = serializers.BooleanField()
    flow_type                = serializers.CharField(allow_null=True)
    phones                   = PatientPhoneSerializer(many=True, required=False)
    created_at               = serializers.DateTimeField()
    updated_at               = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Contratos  &  Parcelas
# ───────────────────────────────────────────────
class PaymentMethodSerializer(serializers.Serializer):
    id                       = serializers.UUIDField()
    oralsin_payment_method_id = serializers.IntegerField()
    name                     = serializers.CharField()
    created_at               = serializers.DateTimeField()


class ContractSerializer(serializers.Serializer):
    id                     = serializers.UUIDField()
    oralsin_contract_id    = serializers.IntegerField(allow_null=True)
    patient_id             = serializers.UUIDField()
    clinic_id              = serializers.UUIDField()
    status                 = serializers.CharField()
    contract_version       = serializers.CharField(allow_blank=True, allow_null=True)
    remaining_installments = serializers.IntegerField(allow_null=True)
    overdue_amount         = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    final_contract_value   = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    do_notifications       = serializers.BooleanField()
    do_billings            = serializers.BooleanField()     
    first_billing_date     = serializers.DateField(allow_null=True)
    negotiation_notes      = serializers.CharField(allow_blank=True, allow_null=True)
    payment_method         = PaymentMethodSerializer(allow_null=True)
    created_at             = serializers.DateTimeField()
    updated_at             = serializers.DateTimeField()


class InstallmentSerializer(serializers.Serializer):
    id                       = serializers.UUIDField()
    contract_id              = serializers.UUIDField()
    contract_version         = serializers.IntegerField(allow_null=True)
    installment_number       = serializers.IntegerField()
    oralsin_installment_id   = serializers.IntegerField(allow_null=True)
    due_date                 = serializers.DateField()
    installment_amount       = serializers.DecimalField(max_digits=14, decimal_places=2)
    received                 = serializers.BooleanField()
    installment_status       = serializers.CharField(allow_blank=True, allow_null=True)
    payment_method           = PaymentMethodSerializer(allow_null=True)
    is_current               = serializers.BooleanField()
    created_at               = serializers.DateTimeField()
    updated_at               = serializers.DateTimeField()


# ───────────────────────────────────────────────
# Fluxo de cobrança
# ───────────────────────────────────────────────
class FlowStepConfigSerializer(serializers.Serializer):
    id            = serializers.UUIDField()
    step_number   = serializers.IntegerField()
    channels      = serializers.ListField(child=serializers.CharField())
    active        = serializers.BooleanField()
    description   = serializers.CharField(allow_blank=True, allow_null=True)
    cooldown_days = serializers.IntegerField()
    created_at    = serializers.DateTimeField()
    updated_at    = serializers.DateTimeField()


class MessageSerializer(serializers.Serializer):
    id         = serializers.UUIDField()
    type       = serializers.CharField()
    content    = serializers.CharField()
    step       = serializers.IntegerField()
    clinic_id  = serializers.UUIDField(allow_null=True)
    is_default = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ContactScheduleSerializer(serializers.Serializer):
    id                   = serializers.UUIDField()
    patient_id           = serializers.UUIDField()
    contract_id          = serializers.UUIDField(allow_null=True)
    clinic_id            = serializers.UUIDField()
    notification_trigger = serializers.CharField()
    advance_flow         = serializers.BooleanField()
    current_step         = serializers.IntegerField()
    channel              = serializers.CharField()
    scheduled_date       = serializers.DateTimeField()
    status               = serializers.CharField(allow_blank=True, allow_null=True)
    created_at           = serializers.DateTimeField()
    updated_at           = serializers.DateTimeField()


class ContactHistorySerializer(serializers.Serializer):
    id                   = serializers.UUIDField()
    patient_id           = serializers.UUIDField()
    contract_id          = serializers.UUIDField(allow_null=True)
    clinic_id            = serializers.UUIDField()
    notification_trigger = serializers.CharField()
    advance_flow         = serializers.BooleanField()
    contact_type         = serializers.CharField()
    sent_at              = serializers.DateTimeField(allow_null=True)
    duration_ms          = serializers.IntegerField(allow_null=True)
    feedback_status      = serializers.CharField(allow_blank=True, allow_null=True)
    success              = serializers.BooleanField()  
    observation          = serializers.CharField(allow_blank=True, allow_null=True)
    message_id           = serializers.UUIDField(allow_null=True)
    schedule_id          = serializers.UUIDField(allow_null=True)
    created_at           = serializers.DateTimeField()
    updated_at           = serializers.DateTimeField()

class ClinicWithDetailsSerializer(serializers.Serializer):
    """
    Serializa uma UserClinic (relação usuário→clínica),
    expondo os dados da clínica e seus detalhes.
    """
    # campos básicos de Clinic
    id                = serializers.UUIDField(source="clinic.id")
    oralsin_clinic_id = serializers.IntegerField(source="clinic.oralsin_clinic_id")
    name              = serializers.CharField(source="clinic.name")
    cnpj              = serializers.CharField(source="clinic.cnpj", allow_blank=True, allow_null=True)
    created_at        = serializers.DateTimeField(source="clinic.created_at")
    updated_at        = serializers.DateTimeField(source="clinic.updated_at")

    # detalhes de ClinicData (OneToOneField related_name="data")
    data = ClinicDataSerializer(source="clinic.data", allow_null=True, read_only=True)

    # telefones (ForeignKey related_name="phones")
    phones = ClinicPhoneSerializer(source="clinic.phones", many=True, read_only=True)



class UserFullDataSerializer(UserSerializer):
    """
    Serializer para o Usuário que estende o UserSerializer
    para incluir as clínicas com todos os seus detalhes.
    """
    clinics = ClinicWithDetailsSerializer(many=True, read_only=True)
    
class PendingCallSerializer(serializers.Serializer):
    id              = serializers.UUIDField()
    patient_id      = serializers.UUIDField()
    contract_id     = serializers.UUIDField()
    clinic_id       = serializers.UUIDField()
    schedule_id     = serializers.UUIDField(allow_null=True)
    current_step    = serializers.IntegerField()
    scheduled_at    = serializers.DateTimeField()
    last_attempt_at = serializers.DateTimeField(allow_null=True)
    attempts        = serializers.IntegerField()
    status          = serializers.CharField()
    result_notes    = serializers.CharField(allow_null=True)
    
class BillingSettingsSerializer(serializers.Serializer):
    clinic_id         = serializers.UUIDField()
    min_days_overdue  = serializers.IntegerField()
    
    
class PendingSyncSerializer(serializers.Serializer):
    id             = serializers.UUIDField()
    object_type    = serializers.CharField()
    object_api_id  = serializers.IntegerField(allow_null=True)
    action         = serializers.CharField()
    new_data       = serializers.JSONField()
    old_data       = serializers.JSONField(allow_null=True)
    status         = serializers.CharField()
    processed_at   = serializers.DateTimeField(allow_null=True)
    created_at     = serializers.DateTimeField()
    updated_at     = serializers.DateTimeField()



class CollectionCaseSerializer(serializers.Serializer):
    id               = serializers.UUIDField()
    patient_id       = serializers.UUIDField()
    contract_id      = serializers.UUIDField()
    installment_id   = serializers.UUIDField()
    clinic_id        = serializers.UUIDField()
    opened_at        = serializers.DateTimeField()
    amount           = serializers.DecimalField(max_digits=14, decimal_places=2)
    deal_id          = serializers.IntegerField(allow_null=True)
    deal_sync_status = serializers.ChoiceField(
        choices=CollectionCase.DealSyncStatus.choices
    )
    status           = serializers.ChoiceField(
        choices=CollectionCase.Status.choices
    )
    

class LetterListItemSerializer(serializers.Serializer):
    """Serializer para exibir um item na lista de cartas."""
    id = serializers.UUIDField(read_only=True)
    patient_name = serializers.CharField(max_length=200)
    contract_id = serializers.CharField(max_length=50)
    status = serializers.CharField(max_length=50)
    relevant_date = serializers.DateTimeField()
    item_type = serializers.CharField(max_length=20)