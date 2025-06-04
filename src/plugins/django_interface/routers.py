from rest_framework.routers import DefaultRouter

from .views.core_views import (
    AddressViewSet,
    ClinicDataViewSet,
    ClinicPhoneViewSet,
    ClinicViewSet,
    ContactHistoryViewSet,
    ContactScheduleViewSet,
    ContractViewSet,
    CoveredClinicViewSet,
    InstallmentViewSet,
    MessageViewSet,
    PatientViewSet,
    UserClinicViewSet,
    UserViewSet,
)

# lista de (rota, ViewSet)
RESOURCES = [
    ("addresses",          AddressViewSet),
    ("clinics",            ClinicViewSet),
    ("clinics-data",       ClinicDataViewSet),
    ("clinic-phones",      ClinicPhoneViewSet),
    ("contact-history",    ContactHistoryViewSet),
    ("contact-schedules",  ContactScheduleViewSet),
    ("contracts",          ContractViewSet),
    ("installments",       InstallmentViewSet),
    ("coverage-clinics",   CoveredClinicViewSet),
    ("patients",           PatientViewSet),
    ("users",              UserViewSet),
    ("user-clinics",       UserClinicViewSet),
    ("messages",           MessageViewSet),
]

def build_router() -> DefaultRouter:
    router = DefaultRouter(trailing_slash=False)
    # Registra todos os CRUDs
    for prefix, viewset in RESOURCES:
        router.register(prefix, viewset, basename=prefix.replace('-', '_'))
    return router
