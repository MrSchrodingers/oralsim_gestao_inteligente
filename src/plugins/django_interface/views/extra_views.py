from dataclasses import asdict

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from oralsin_core.adapters.config.composition_root import container as core_container
from oralsin_core.core.application.queries.dashboard_queries import GetDashboardSummaryQuery
from oralsin_core.core.application.queries.patient_queries import ListPatientsQuery
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from notification_billing.adapters.config.composition_root import container as nb_container
from notification_billing.core.application.commands.notification_commands import (
    RunAutomatedNotificationsCommand,
    SendManualNotificationCommand,
)
from plugins.django_interface.models import User
from plugins.django_interface.permissions import IsClinicUser
from plugins.django_interface.serializers.core_serializers import PatientSerializer, UserSerializer
from plugins.django_interface.views.core_views import PaginationFilterMixin

core_query_bus = core_container.query_bus()
nb_command_bus = nb_container.command_bus()

# ─── TTLs em segundos ───────────────────────────────────────────────────────
DASHBOARD_TTL      = 60    # resumo do dashboard, muda com frequência moderada
ME_TTL             = 300   # perfil do usuário, muda raramente
USERS_FULL_TTL     = 600   # lista completa de usuários, muda pouco
PATIENTS_DATA_TTL  = 60    # listagem de pacientes, muda conforme sync

# ─── Helpers de key_prefix ─────────────────────────────────────────────────
def cache_key_prefix_for(prefix: str):
    def _key(request, *args, **kwargs):
        uid = getattr(request.user, "id", "anon")
        return f"{prefix}_user_{uid}"
    return _key

def patients_data_cache_key(request, *args, **kwargs):
    clinic = getattr(request.user, "clinic_id", "anon")
    # garante que filtros e paginação entram na chave
    params = "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))
    return f"patients_data_clinic_{clinic}_{params}"

# ╭──────────────────────────────────────────────╮
# │      DASHBOARD SUMMARY                     │
# ╰──────────────────────────────────────────────╯
@method_decorator(
    cache_page(DASHBOARD_TTL, key_prefix=cache_key_prefix_for("dashboard_summary")),
    name="get",
)
class DashboardSummaryView(PaginationFilterMixin, APIView):
    permission_classes = [IsClinicUser]
    
    def get(self, request):
        filtros = self._filters(request)
        
        q = GetDashboardSummaryQuery(filtros=filtros, user_id=str(request.user.id))
        res = core_query_bus.dispatch(q)
        return Response(asdict(res))


# ╭──────────────────────────────────────────────╮
# │      RUN / SEND NOTIFICATIONS (POST)        │
# ╰──────────────────────────────────────────────╯
class RunAutomatedNotificationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data
        cmd = RunAutomatedNotificationsCommand(
            clinic_id=payload.get("clinic_id"),
            batch_size=int(payload.get("batch_size", 10)),
            only_pending=payload.get("only_pending", True),
            channel=payload.get("channel"),
        )
        res = nb_command_bus.dispatch(cmd)
        return Response(res, status=status.HTTP_200_OK)


class SendManualNotificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data
        cmd = SendManualNotificationCommand(
            patient_id=payload.get("patient_id"),
            contract_id=payload.get("contract_id"),
            channel=payload.get("channel"),
            message_id=payload.get("message_id"),
        )
        res = nb_command_bus.dispatch(cmd)
        return Response(res, status=status.HTTP_200_OK)


# ╭──────────────────────────────────────────────╮
# │           ME / USERS INFO                   │
# ╰──────────────────────────────────────────────╯
@method_decorator(
    cache_page(ME_TTL, key_prefix=cache_key_prefix_for("me")),
    name="get",
)
class MeView(APIView):
    permission_classes = [IsClinicUser]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


@method_decorator(
    cache_page(USERS_FULL_TTL, key_prefix=cache_key_prefix_for("users_full")),
    name="get",
)
class UsersFullDataView(APIView):
    permission_classes = [IsClinicUser]

    def get(self, request):
        users = User.objects.all().prefetch_related("clinics")
        results = []
        for u in users:
            clinics = [str(link.clinic_id) for link in u.clinics.all()]
            data = UserSerializer(u).data
            data["clinics"] = clinics
            results.append(data)
        return Response({"results": results, "total": len(results)})


# ╭──────────────────────────────────────────────╮
# │        PATIENTS DATA (lightweight list)      │
# ╰──────────────────────────────────────────────╯
@method_decorator(
    cache_page(PATIENTS_DATA_TTL, key_prefix=patients_data_cache_key),
    name="get",
)
class PatientsDataView(APIView):
    permission_classes = [IsClinicUser]

    def get(self, request):
        q = ListPatientsQuery(
            filtros=request.query_params.dict(),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 50)),
        )
        res = core_query_bus.dispatch(q)
        data = PatientSerializer(res.items, many=True).data
        return Response({"results": data, "total": res.total})
