import io
from dataclasses import asdict
from datetime import date, timedelta

from django.http import FileResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from oralsin_core.adapters.config.composition_root import container as core_container
from oralsin_core.core.application.queries.dashboard_queries import GetDashboardReportQuery, GetDashboardSummaryQuery
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from notification_billing.adapters.config.composition_root import container as nb_container
from notification_billing.core.application.commands.notification_commands import (
    RunAutomatedNotificationsCommand,
    SendManualNotificationCommand,
)
from notification_billing.core.application.queries.letter_queries import GetLetterPreviewQuery, ListLettersQuery
from plugins.django_interface.models import User
from plugins.django_interface.permissions import IsAdminUser, IsClinicUser
from plugins.django_interface.serializers.core_serializers import LetterListItemSerializer, UserFullDataSerializer, UserSerializer
from plugins.django_interface.views.core_views import PaginationFilterMixin

core_query_bus  = core_container.query_bus()
nb_query_bus    = nb_container.query_bus()
nb_command_bus  = nb_container.command_bus()

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

        # ───── novo: converte string → date ─────
        period_days = int(request.query_params.get("period_days", 0))
        if period_days:
            filtros["start_date"] = (date.today() - timedelta(days=period_days)).isoformat()
            filtros["end_date"]   = date.today().isoformat()
        else:
            filtros["start_date"] = request.query_params.get("start_date")  
            filtros["end_date"]   = request.query_params.get("end_date")    
        
        q = GetDashboardSummaryQuery(filtros=filtros, user_id=str(request.user.id))
        res = core_query_bus.dispatch(q)
        return Response(asdict(res))


class DashboardReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        filtros = {
            "start_date": request.query_params.get("start_date"),
            "end_date": request.query_params.get("end_date"),
        }
        q = GetDashboardReportQuery(user_id=str(request.user.id), filtros=filtros)
        pdf_bytes = core_query_bus.dispatch(q)

        filename = f"relatorio_dashboard_{date.today().isoformat()}.pdf"
        response = FileResponse(io.BytesIO(pdf_bytes), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    
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
# │              ME / USERS INFO                 │
# ╰──────────────────────────────────────────────╯
@method_decorator(
    cache_page(ME_TTL, key_prefix=cache_key_prefix_for("me")),
    name="get",
)
class MeView(APIView):
    """
    View para retornar os dados do usuário logado.
    Se o usuário for do tipo 'clinic', anexa as informações
    detalhadas de suas clínicas (UserClinics, ClinicData, ClinicPhone).
    """
    permission_classes = [IsClinicUser]

    def get(self, request):
        user = request.user

        # Se for um usuário de clínica, retorna os dados completos com clínicas
        if user.role == "clinic":
            user_instance = User.objects.prefetch_related(
                "clinics__clinic__data__address",  
                "clinics__clinic__phones"
            ).get(pk=user.id)
            serializer = UserFullDataSerializer(user_instance)
            return Response(serializer.data)

        serializer = UserSerializer(user)
        return Response(serializer.data)


@method_decorator(
    cache_page(USERS_FULL_TTL, key_prefix=cache_key_prefix_for("users_full")),
    name="get",
)
class UsersFullDataView(APIView):
    """
    View para retornar os dados de todos os usuários com suas
    respectivas clínicas e detalhes.
    - Otimizada para usar o UserFullDataSerializer e prefetch_related.
    - Permissão alterada para IsAdminUser para maior segurança.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Busca todos os usuários e otimiza a query para já trazer
        # os dados relacionados de clínicas, data e phones.
        users = User.objects.prefetch_related(
            "clinics__clinic__data__address",
            "clinics__clinic__phones"
        ).all()

        # O serializer agora cuida de toda a montagem dos dados aninhados
        serializer = UserFullDataSerializer(users, many=True)
        
        return Response({"results": serializer.data, "total": len(serializer.data)})
    
class LetterListView(APIView, PaginationFilterMixin):
    """
    View para listar todas as cartas enviadas e agendadas, com suporte a paginação.
    Exemplo: /api/letters/?page=1&page_size=20
    """
    # Adicionamos a permissão para garantir que o usuário está autenticado
    permission_classes = [IsClinicUser]

    def get(self, request, *args, **kwargs):
        filtros = self._filters(request)
        page, page_size = self._pagination(request)

        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)

        query = ListLettersQuery(filtros=filtros, page=page, page_size=page_size)
        try:
            paged_result = nb_query_bus.dispatch(query)
            
            serializer = LetterListItemSerializer(paged_result.items, many=True)
            
            payload = {
                "results": serializer.data,
                "total_items": paged_result.total,
                "page": paged_result.page,
                "page_size": paged_result.page_size,
                "total_pages": paged_result.total_pages,
                "items_on_page": len(paged_result.items),
            }
            
            return Response(payload, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class LetterPreviewView(APIView, PaginationFilterMixin):
    """
    View para gerar e retornar o arquivo .docx de uma carta específica.
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, item_id, item_type, *args, **kwargs):
        filtros = self._filters(request)
        if getattr(request.user, "clinic_id", None):
            filtros["clinic_id"] = str(request.user.clinic_id)

        query = GetLetterPreviewQuery(filtros=filtros, item_id=item_id, item_type=item_type)

        try:
            docx_stream = nb_query_bus.dispatch(query)

            response = HttpResponse(
                docx_stream.read(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            filename = f"preview_{item_type}_{item_id}.docx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            return response
        except FileNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)