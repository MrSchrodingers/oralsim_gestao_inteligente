from django.utils import timezone
from oralsin_core.adapters.repositories.user_repo_impl import UserRepoImpl
from oralsin_core.adapters.security.hash_service import HashService
from oralsin_core.adapters.security.jwt_service import JWTService
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from config import settings
from plugins.django_interface.models import UserClinic


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        if not email or not password:
            return Response({"detail": "Credenciais incompletas."},
                            status=status.HTTP_400_BAD_REQUEST)

        user_repo = UserRepoImpl()
        user = user_repo.find_by_email(email)
        if not user or not HashService.verify(password, user.password_hash):
            return Response({"detail": "E-mail ou senha inválidos."},
                            status=status.HTTP_401_UNAUTHORIZED)

        # Gera JWT
        clinic_id: str | None = None
        if user.role == "clinic":
            link = UserClinic.objects.filter(user_id=user.id).first()
            if link:
                clinic_id = str(link.clinic_id)
                
        jwt = JWTService.create_token(
            subject=str(user.id),
            expires_in=settings.JWT_EXPIRES_IN,
            role=user.role,
            clinic_id=clinic_id,
        )
        resp = Response({"message": "Autenticado com sucesso."}, status=status.HTTP_200_OK)
        # Configura cookie seguro
        resp.set_cookie(
            settings.AUTH_COOKIE_NAME,
            jwt,
            secure=settings.AUTH_COOKIE_SECURE,
            httponly=settings.AUTH_COOKIE_HTTPONLY,
            samesite=settings.AUTH_COOKIE_SAMESITE,
            expires=timezone.now() + timezone.timedelta(seconds=settings.JWT_EXPIRES_IN),
        )
        return resp


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        resp = Response({"message": "Logout realizado."}, status=status.HTTP_200_OK)
        # Destroi cookie
        resp.delete_cookie(settings.AUTH_COOKIE_NAME)
        return resp

class HealthCheckView(APIView):
    """
    Rota GET /api/healthz/ — retorna status 200 se a API estiver viva.
    """
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)