"""
Dominio → ORM, versão 2025-05-22  
Revisão focada em:

⚑ Padronização dos IDs externos (`oralsin_*_id`)  
⚑ Chaves estrangeiras obrigatórias entre entidades correlatas  
⚑ Unicidade e consistência (UK + CHECK)  
⚑ Índices BRIN/GiN onde há benefício real  
"""

from __future__ import annotations

import uuid

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import BrinIndex, GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Index, Q, UniqueConstraint
from django.db.models.functions import Lower


# ╭──────────────────────────────────────────────╮
# │ 0. Métodos de Pagamento                     │
# ╰──────────────────────────────────────────────╯
class PaymentMethod(models.Model):
    """
    Tabela de formas de pagamento (cacheada da Oralsin).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oralsin_payment_method_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_methods"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# ╭──────────────────────────────────────────────╮
# │ 1. Autenticação / Acesso                    │
# ╰──────────────────────────────────────────────╯
class User(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CLINIC = "clinic", "Clinic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, max_length=128)
    password_hash = models.CharField(max_length=128)
    name = models.CharField(max_length=100)
    clinic_name = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLINIC,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        indexes = [
            Index(Lower("email"), name="user_email_lower_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"


# ╭──────────────────────────────────────────────╮
# │ 2. Clínicas                                 │
# ╰──────────────────────────────────────────────╯
class Clinic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oralsin_clinic_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255, blank=True, null=True)
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinics"
        constraints = [
            UniqueConstraint(Lower("name"), name="uq_clinic_name_lower")
        ]
        indexes = [
            BrinIndex(fields=["created_at"], autosummarize=True),
        ]

    def __str__(self) -> str:
        return self.name


class CoveredClinic(models.Model):
    """
    Registro de franquias habilitadas para cobrança.
    Sempre há vínculo 1-para-1 com Clinic.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.OneToOneField(
        Clinic, on_delete=models.CASCADE, related_name="coverage"
    )
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # mirror seguro para debug / queries rápidas
    oralsin_clinic_id = models.IntegerField(
        unique=True,
        db_index=True,
        editable=False,
    )
    name = models.CharField(max_length=255, editable=False)
    corporate_name = models.CharField(max_length=255, blank=True, null=True)
    acronym = models.CharField(max_length=50, blank=True, null=True)
    cnpj = models.CharField(max_length=18, blank=True, null=True)

    class Meta:
        db_table = "covered_clinics"
        indexes = [Index(fields=["name"])]

    def save(self, *args, **kwargs):  # noqa: D401
        if not self.oralsin_clinic_id and self.clinic_id:
            self.oralsin_clinic_id = self.clinic.oralsin_clinic_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    street = models.CharField(max_length=200)
    number = models.CharField(max_length=50)
    complement = models.CharField(max_length=100, blank=True, null=True)
    neighborhood = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "addresses"
        constraints = [
            UniqueConstraint(
                Lower("street"), 
                "number", 
                "zip_code", 
                name="uq_address_street_number_zip"
            )
        ]
        indexes = [
            Index(fields=["city"]),
            Index(fields=["state"]),
            BrinIndex(fields=["created_at"], autosummarize=True),
        ]

    def __str__(self) -> str:
        return f"{self.street}, {self.number} – {self.city}/{self.state}"


class ClinicData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.OneToOneField(
        Clinic, on_delete=models.CASCADE, related_name="data"
    )
    corporate_name = models.CharField(max_length=255, blank=True, null=True)
    acronym = models.CharField(max_length=50, blank=True, null=True)
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="clinics",
    )
    active = models.BooleanField(default=True, db_index=True)
    franchise = models.BooleanField(default=False, db_index=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)
    first_billing_date = models.DateField(blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinics_data"

    def __str__(self) -> str:
        return f"Meta {self.clinic.name}"


class ClinicPhone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="phones"
    )
    phone_number = models.CharField(max_length=20)
    phone_type = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinic_phones"
        indexes = [Index(fields=["clinic"]), Index(fields=["phone_type"])]

    def __str__(self) -> str:
        return f"{self.phone_number} ({self.phone_type})"


# ╭──────────────────────────────────────────────╮
# │ 3. Pacientes & Contratos                    │
# ╰──────────────────────────────────────────────╯
class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oralsin_patient_id = models.IntegerField(
        blank=True, null=True, unique=True, db_index=True
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="patients"
    )
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200, blank=True, null=True)
    cpf = models.CharField(max_length=14, blank=True, null=True)
    email = models.EmailField(blank=True, null=True, db_index=True)
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="patients",
    )
    name_search_vector = SearchVectorField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def flow_type(self) -> str | None:
        """Return patient's billing flow based on related records."""
        if self.collectioncase_set.exists():
            return "cordial_billing"
        if self.schedules.exists():
            return "notification_billing"
        return None
    
    class Meta:
        db_table = "patients"
        indexes = [
            GinIndex(fields=["name_search_vector"]),
            BrinIndex(fields=["created_at"], autosummarize=True),
        ]

    def __str__(self) -> str:
        return self.name


class PatientPhone(models.Model):
    class Type(models.TextChoices):
        HOME = "home", "Residencial"
        MOBILE = "mobile", "Celular"
        COMMERCIAL = "commercial", "Comercial"
        CONTACT = "contact", "Contato"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="phones"
    )
    phone_number = models.CharField(max_length=20)
    phone_type = models.CharField(
        max_length=12, choices=Type.choices, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patient_phones"
        indexes = [Index(fields=["patient"]), Index(fields=["phone_type"])]

    def __str__(self) -> str:
        return f"{self.phone_number} ({self.phone_type})"


class Contract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oralsin_contract_id = models.IntegerField(blank=True, null=True, db_index=True)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="contracts"
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="contracts"
    )
    status = models.CharField(
        max_length=10,
        choices=[("ativo", "Ativo"), ("inativo", "Inativo"), ("cancelado", "Cancelado")],
        default="ativo",
        db_index=True,
    )
    contract_version = models.CharField(max_length=10, blank=True, null=True)
    remaining_installments = models.PositiveIntegerField(blank=True, null=True)
    overdue_amount = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    final_contract_value = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    do_notifications = models.BooleanField(default=True, db_index=True)
    do_billings = models.BooleanField(default=False, db_index=True)
    first_billing_date = models.DateField(blank=True, null=True, db_index=True)
    negotiation_notes = models.TextField(blank=True, null=True)
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="contracts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contracts"
        unique_together = [
            ("oralsin_contract_id", "contract_version", "patient"),
        ]
        indexes = [
            Index(fields=["clinic", "patient"]),
            Index(fields=["status"]),
            BrinIndex(fields=["first_billing_date"], autosummarize=True),
        ]

    def __str__(self) -> str:
        return f"Contrato {self.oralsin_contract_id or self.id}"


class Installment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="installments"
    )
    contract_version = models.CharField(max_length=10, null=True, db_index=True)
    installment_number = models.PositiveIntegerField()
    oralsin_installment_id = models.IntegerField(unique=True, null=True, db_index=True)
    due_date = models.DateField(db_index=True)
    installment_amount = models.DecimalField(max_digits=14, decimal_places=2)
    received = models.BooleanField(default=False, db_index=True)
    installment_status = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="installments"
    )
    is_current = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "installments"
        unique_together = [
            ("contract", "oralsin_installment_id")
        ]
        indexes = [
            Index(fields=["contract", "contract_version", "installment_number", "is_current"]),
            BrinIndex(fields=["due_date"], autosummarize=True),
            Index(
                fields=["received", "due_date"],
                name="inst_overdue_idx",
                condition=Q(received=False),
            ),
            # índice parcial para parcelas ativas não recebidas
            Index(
                name="inst_current_overdue_idx",
                fields=["due_date"],
                condition=Q(is_current=True, received=False),
            ),
            # índice simples de is_current por contrato
            Index(
                name="inst_contract_current_idx",
                fields=["contract", "is_current"],
            ),
        ]
        constraints = [
            UniqueConstraint(
                fields=["contract", "contract_version"],
                condition=Q(is_current=True),
                name="unique_current_per_contract_version",
            )
        ]

    def __str__(self) -> str:
        return f"Parcela {self.installment_number} | {self.contract}"


# ╭──────────────────────────────────────────────╮
# │ 4. Fluxos de Cobrança / Notificações         │
# ╰──────────────────────────────────────────────╯
class FlowStepConfig(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "E-mail"
        PHONECALL = "phonecall", "Ligação"
        LETTER = "letter", "Carta"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step_number = models.PositiveIntegerField(unique=True)
    channels = ArrayField(
        models.CharField(max_length=20, choices=Channel.choices), default=list
    )
    cooldown_days = models.PositiveIntegerField(default=7)
    active = models.BooleanField(default=True, db_index=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "flow_step_config"
        ordering = ["step_number"]
        indexes = [
            GinIndex(fields=["channels"]),
        ]

    def __str__(self) -> str:
        return f"Step {self.step_number}"


class Message(models.Model):
    class Type(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=Type.choices)
    content = models.TextField()
    step = models.PositiveIntegerField()
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="messages",
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "messages"
        unique_together = [("type", "step", "clinic")]
        indexes = [Index(fields=["type", "step"])]

    def __str__(self) -> str:
        return f"{self.type} (step {self.step})"


class ContactSchedule(models.Model):
    class Trigger(models.TextChoices):
        AUTOMATED = "automated", "Automatizado"
        MANUAL = "manual", "Manual"
        
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        PROCESSING  = "processing", "Processando"
        REJECTED = "rejected", "Rejeitado"
        CANCELED = "cancelled_paid", "Cancelado por Pagamento"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="schedules"
    )
    installment = models.ForeignKey(
        Installment,
        on_delete=models.SET_NULL,   
        blank=True,
        null=True,
        related_name="schedules",
        db_index=True,
    )
    contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="schedules",
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="schedules"
    )
    notification_trigger = models.CharField(
        max_length=20, choices=Trigger.choices, default=Trigger.AUTOMATED
    )
    advance_flow = models.BooleanField(default=False)
    current_step = models.PositiveIntegerField()
    channel = models.CharField(max_length=20)
    scheduled_date = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contact_schedules"
        indexes = [
            Index(fields=["clinic", "scheduled_date"]),
            models.Index(fields=["installment"]),
            BrinIndex(fields=["scheduled_date"], autosummarize=True),
        ]
        constraints = [
            UniqueConstraint(
                fields=["patient", "contract", "current_step", "channel", "installment"],
                condition=Q(status="pending"),
                name="uq_schedule_pending_per_step"
            ),
            UniqueConstraint(
                fields=["patient", "channel"],
                condition=Q(status="pending", notification_trigger="automated"),
                name="uq_patient_channel_pending",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.patient} → step {self.current_step}"


class ContactHistory(models.Model):
    class Type(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Trigger(models.TextChoices):
        AUTOMATED = "automated", "Automatizado"
        MANUAL = "manual", "Manual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="history"
    )
    contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="history",
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="history"
    )
    notification_trigger = models.CharField(
        max_length=20, choices=Trigger.choices, default=Trigger.AUTOMATED
    )
    advance_flow = models.BooleanField(default=False)
    contact_type = models.CharField(max_length=20, choices=Type.choices)
    sent_at = models.DateTimeField(blank=True, null=True, db_index=True)
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    feedback_status = models.CharField(max_length=50, blank=True, null=True)
    success = models.BooleanField(
        default=True,
        help_text="Indica se o contato foi concluído sem erros"
    )
    observation = models.TextField(blank=True, null=True)
    observation_search_vector = SearchVectorField(null=True)
    message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="history",
    )
    schedule = models.ForeignKey(
        ContactSchedule,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="history",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contact_history"
        constraints = [
            UniqueConstraint(
                fields=["schedule", "contact_type", "advance_flow"],
                name="uq_history_schedule_channel_step",
            ),
            UniqueConstraint(
                fields=["schedule"],
                condition=Q(status="sent"),
                name="uq_history_sent_per_schedule"
            )
        ]
        indexes = [
            Index(fields=["clinic", "sent_at", "contact_type", "success"]),
            BrinIndex(fields=["sent_at"], autosummarize=True),
            GinIndex(fields=["observation_search_vector"]),
        ]

    def __str__(self) -> str:
        return f"{self.patient} @ {self.sent_at}"


# ╭──────────────────────────────────────────────╮
# │ 5. Vínculo Usuário ↔ Clínica                 │
# ╰──────────────────────────────────────────────╯
class UserClinic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="clinics"
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="users"
    )
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_clinics"
        unique_together = [("user", "clinic")]
        indexes = [Index(fields=["clinic"])]

    def __str__(self) -> str:
        return f"{self.user} ⇄ {self.clinic}"


# ╭──────────────────────────────────────────────╮
# │ 6. Motor de Pending Sync                     │
# ╰──────────────────────────────────────────────╯
class PendingSync(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Rejeitado"
        APPLIED = "applied", "Aplicado"

    class ObjectType(models.TextChoices):
        CLINIC = "clinic", "Clinic"
        PATIENT = "patient", "Patient"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object_type = models.CharField(max_length=20, choices=ObjectType.choices)
    object_api_id = models.IntegerField(blank=True, null=True)
    action = models.CharField(max_length=50)
    new_data = models.JSONField()
    old_data = models.JSONField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pending_sync"
        indexes = [
            GinIndex(fields=["new_data"]),
            GinIndex(fields=["old_data"]),
            Index(fields=["status"]),
            Index(fields=["object_type"]),
            Index(
                fields=["created_at"],
                name="pending_recent_pending_idx",
                condition=Q(status="pending"),
            ),
            BrinIndex(fields=["created_at"], autosummarize=True),
        ]

    def __str__(self) -> str:
        return f"[{self.status}] {self.object_type}:{self.object_api_id}"

# ╭──────────────────────────────────────────────╮
# │ 7. Caso de Coleta                            │
# ╰──────────────────────────────────────────────╯
class CollectionCase(models.Model):
    class DealSyncStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        CREATED = "created", "Criado"
        UPDATED = "updated", "Atualizado"
        ERROR = "error", "Erro"

    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        CLOSED = "closed", "Fechado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    installment = models.ForeignKey(Installment, on_delete=models.CASCADE)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    stage_id = models.IntegerField(
        blank=True,
        null=True,
        help_text="ID da etapa do negócio no Pipedrive",
    )
    opened_at = models.DateTimeField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    deal_id = models.BigIntegerField(blank=True, null=True)
    deal_sync_status = models.CharField(
        max_length=20,
        choices=DealSyncStatus.choices,
        default=DealSyncStatus.PENDING,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    class Meta:
        db_table = "collection_cases"
        indexes = [models.Index(fields=["clinic", "status", "patient", "deal_id", "installment", "deal_sync_status"])]


class PendingCall(models.Model):
    """
    Ligações pendentes geradas por steps cujo canal inclui 'phonecall'.
    A pendência é resolvida por atendentes humanos ou robocall externo.
    """
    class Status(models.TextChoices):
        PENDING   = "pending",  "Pendente"
        DONE      = "done",     "Concluída"
        FAILED    = "failed",   "Falhou"

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient       = models.ForeignKey(Patient,  on_delete=models.CASCADE, related_name="pending_calls")
    contract      = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="pending_calls")
    clinic        = models.ForeignKey(Clinic,   on_delete=models.CASCADE, related_name="pending_calls")
    schedule      = models.ForeignKey(
        ContactSchedule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pending_calls"
    )
    current_step  = models.PositiveIntegerField()
    scheduled_at  = models.DateTimeField(help_text="Quando a ligação deve ser feita", db_index=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    attempts      = models.PositiveIntegerField(default=0)
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    result_notes  = models.TextField(blank=True, null=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pending_calls"
        indexes = [
            Index(fields=["clinic", "status"]),
            BrinIndex(fields=["scheduled_at"], autosummarize=True),
        ]
        constraints = [
            UniqueConstraint(
                fields=["patient", "contract", "current_step"],
                condition=Q(status="pending"),
                name="uq_pending_phonecall_per_step",
            )
        ]

    def __str__(self) -> str:     # pragma: no cover
        return f"{self.patient} → ligação step {self.current_step}"
    
    
class BillingSettings(models.Model):
    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.OneToOneField(
        Clinic, on_delete=models.CASCADE, related_name="billing_settings"
    )
    min_days_overdue = models.PositiveIntegerField(
        default=90,
        help_text="Dias mínimos de atraso para escalonar dívida"
    )
    class Meta:
        db_table = "billing_settings"


class PipeboardActivitySent(models.Model):
    """Mantém controle das atividades do Pipeboard já processadas."""

    activity_id = models.BigIntegerField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pipeboard_activity_sent"
        
        
class RegistrationRequest(models.Model):
    """Stores registration requests from new clinics for admin approval."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=128)
    password_hash = models.CharField(max_length=128, help_text="Store hashed passwords only")
    name = models.CharField(max_length=100, help_text="Full name of the requester")
    password_enc  = models.CharField(    
        max_length=256,
        help_text="Senha em texto-claro, cifrada com Fernet; será apagada após aprovação.",
    )
    clinic_name = models.CharField(max_length=255, help_text="The name of the clinic being registered")
    cordial_billing_config = models.IntegerField(default=90, help_text="Dias mínimos para cobrança amigável")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "registration_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return f"Request from {self.email} for {self.clinic_name} [{self.status}]"
    
class PaymentStatus(models.Model):
    raw_status   = models.CharField(max_length=80, unique=True)
    normalized   = models.CharField(max_length=80, db_index=True)
    is_paid      = models.BooleanField(default=False)
    kind         = models.CharField(max_length=20, default="unknown")  # bank, gateway, manual…
    first_seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_statuses"
        indexes  = [models.Index(fields=["normalized"])]