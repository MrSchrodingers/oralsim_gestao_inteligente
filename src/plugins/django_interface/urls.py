from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from config import settings

from .routers import build_router
from .views.auth_views import HealthCheckView, LoginView, LogoutView

swagger_permissions = [permissions.IsAdminUser] if not settings.DEBUG else [permissions.AllowAny]

schema_view = get_schema_view(
    openapi.Info(
        title="Oralsin Gestão Recebíveis API",
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

    path("swagger/",     schema_view.with_ui("swagger", cache_timeout=0), name="swagger-ui"),
    path("swagger.json", schema_view.without_ui(cache_timeout=0),         name="swagger-json"),
    path("redoc/",       schema_view.with_ui("redoc",   cache_timeout=0), name="redoc-ui"),

    # todas as suas rotas CRUD + healthz
    path("", include(router.urls)),
]
