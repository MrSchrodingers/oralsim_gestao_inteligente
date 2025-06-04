"""
Admin site registry
-------------------
Registra todos os modelos de forma dinâmica, aplicando
as novas nomenclaturas `oralsin_*`.
"""

import structlog
from django.contrib import admin as django_admin

from . import models

logger = structlog.get_logger(__name__)

# ╭──────────────────────────────────────────────╮
# │ Configuração de cada ModelAdmin             │
# ╰──────────────────────────────────────────────╯
MODEL_ADMIN_REGISTRY: dict[type[models.models.Model], dict] = {
    # 0. Payment
    models.PaymentMethod: dict(
        list_display=("oralsin_payment_method_id", "name"),
        search_fields=("name",),
    ),
    # 1. Auth
    models.User: dict(
        list_display=("email", "name", "role", "is_active"),
        search_fields=("email", "name"),
        list_filter=("role", "is_active"),
    ),
    # 2. Clínicas
    models.Clinic: dict(
        list_display=("oralsin_clinic_id", "name", "cnpj", "created_at"),
        search_fields=("name", "oralsin_clinic_id"),
    ),
    models.CoveredClinic: dict(
        list_display=("oralsin_clinic_id", "name", "active"),
        list_filter=("active",),
        search_fields=("name",),
    ),
    models.Address: dict(
        list_display=("street", "city", "state", "zip_code"),
        search_fields=("street", "city", "zip_code"),
    ),
    models.ClinicData: dict(
        list_display=("clinic", "corporate_name", "active"),
        list_filter=("active",),
        search_fields=("corporate_name",),
    ),
    models.ClinicPhone: dict(
        list_display=("clinic", "phone_type", "phone_number"),
        list_filter=("phone_type",),
    ),
    # 3. Pacientes & Contratos
    models.Patient: dict(
        list_display=("name", "cpf", "clinic", "is_notification_enabled"),
        list_filter=("clinic", "is_notification_enabled"),
        search_fields=("name", "cpf"),
    ),
    models.PatientPhone: dict(
        list_display=("patient", "phone_type", "phone_number"),
        list_filter=("phone_type",),
    ),
    models.Contract: dict(
        list_display=(
            "oralsin_contract_id",
            "patient",
            "clinic",
            "status",
            "remaining_installments",
        ),
        list_filter=("status", "clinic"),
        search_fields=("oralsin_contract_id",),
    ),
    models.Installment: dict(
        list_display=("contract", "installment_number", "due_date", "received"),
        list_filter=("received",),
    ),
    # 4. Fluxo / Mensagens
    models.FlowStepConfig: dict(
        list_display=("step_number", "description", "active"),
        list_filter=("active",),
    ),
    models.Message: dict(
        list_display=("type", "step", "is_default", "clinic"),
        list_filter=("type", "step", "clinic"),
        search_fields=("content",),
    ),
    models.ContactSchedule: dict(
        list_display=("patient", "clinic", "current_step", "scheduled_date", "status"),
        list_filter=("clinic", "status"),
    ),
    models.ContactHistory: dict(
        list_display=("patient", "clinic", "sent_at", "contact_type"),
        list_filter=("clinic", "contact_type"),
    ),
    # 5. Segurança
    models.UserClinic: dict(
        list_display=("user", "clinic", "linked_at"),
        list_filter=("clinic",),
    ),
    # 6. Pending Sync
    models.PendingSync: dict(
        list_display=("object_type", "object_api_id", "status"),
        list_filter=("status", "object_type"),
    ),
}

# ╭──────────────────────────────────────────────╮
# │ Registro dinâmico                           │
# ╰──────────────────────────────────────────────╯
for model, opts in MODEL_ADMIN_REGISTRY.items():
    admin_class = type(f"{model.__name__}Admin", (django_admin.ModelAdmin,), opts)
    django_admin.site.register(model, admin_class)
    logger.debug("Registered model in admin", model=model.__name__)
