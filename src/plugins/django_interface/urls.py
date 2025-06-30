from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from config import settings

from .routers import build_router
from .views.auth_views import HealthCheckView, LoginView, LogoutView
from .views.extra_views import AdminClinicSummaryView, DashboardReportView, DashboardSummaryView, LetterListView, LetterPreviewView, MeView, RunAutomatedNotificationsView, SendManualNotificationView, UsersFullDataView

swagger_permissions = [permissions.IsAdminUser] if not settings.DEBUG else [permissions.AllowAny]

schema_view = get_schema_view(
    openapi.Info(
        title="Oralsin Gestão Inteligente",
        default_version="v1",
        description="Camada HTTP da arquitetura CQRS + Bus",
        contact=openapi.Contact(email="suporte@oralsin.com.br"),
        license=openapi.License(name="BSD License"),
    ),
    public=settings.DEBUG,
    permission_classes=swagger_permissions,
)

router = build_router()

urlpatterns = [
    path("login/",  LoginView.as_view(),  name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("healthz/", HealthCheckView.as_view(), name="healthz"),
    path("me/", MeView.as_view(), name="me"),
    path("dashboard-summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("clinics/<uuid:clinic_id>/summary/", AdminClinicSummaryView.as_view(), name="clinic-summary"),
    path("dashboard-report/", DashboardReportView.as_view(), name="dashboard-report"),
    path("notifications/run-automated/", RunAutomatedNotificationsView.as_view(), name="run-automated"),
    path("notifications/send-manual/", SendManualNotificationView.as_view(), name="send-manual"),
    path("users-data/", UsersFullDataView.as_view(), name="users-data"),
    path('letters/', LetterListView.as_view(), name='letter-list'),
    path('letters/<uuid:item_id>/<str:item_type>/preview/', LetterPreviewView.as_view(), name='letter-preview'),
    
    path("swagger/",     schema_view.with_ui("swagger", cache_timeout=0), name="swagger-ui"),
    path("swagger.json", schema_view.without_ui(cache_timeout=0),         name="swagger-json"),
    path("redoc/",       schema_view.with_ui("redoc",   cache_timeout=0), name="redoc-ui"),

    # todas as suas rotas CRUD
    path("", include(router.urls)),
]
