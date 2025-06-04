import jwt
from django.contrib.auth import get_user_model
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from oralsin_core.adapters.security.jwt_service import JWTService

User = get_user_model()

class JWTAuthentication(BaseAuthentication):
    """
    Lê o header Authorization: Bearer <token>,
    valida com o JWTService e retorna (user, token).
    """
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        parts = header.split()

        if not header or parts[0].lower() != "bearer" or len(parts) != 2:  # noqa: PLR2004
            return None 

        token = parts[1]
        try:
            payload = JWTService.decode_token(token)
        except jwt.PyJWTError as e:
            raise exceptions.AuthenticationFailed(f"Token inválido: {e}")  # noqa: B904

        # aqui usamos o sub (subject) como PK ou identificador único
        try:
            user = User.objects.get(pk=payload["sub"])
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed("Usuário não encontrado.")  # noqa: B904

        return (user, token)


class CookieJWTAuthentication(JWTAuthentication):
    """
    Em vez de ler do header, busca o token em um cookie 'jwt'.
    """
    def authenticate(self, request):
        token = request.COOKIES.get("jwt")
        if not token:
            return None
        # reaproveita o decode e lookup do pai
        try:
            payload = JWTService.decode_token(token)
        except jwt.PyJWTError as e:
            raise exceptions.AuthenticationFailed(f"Token inválido: {e}")  # noqa: B904

        try:
            user = User.objects.get(pk=payload["sub"])
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed("Usuário não encontrado.")  # noqa: B904

        return (user, token)
