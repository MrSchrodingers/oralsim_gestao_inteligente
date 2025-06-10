import jwt
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from config import settings
from oralsin_core.adapters.repositories.user_repo_impl import UserRepoImpl
from oralsin_core.adapters.security.jwt_service import JWTService


class SimpleUser:
    """
    Representa um usuário mínimo compatível com DRF,
    usando somente os atributos necessários: id, role, clinic_id e is_authenticated.
    """
    def __init__(self, id: str, role: str | None = None, clinic_id: str | None = None):
        self.id = id
        self.role = role
        self.clinic_id = clinic_id
        self.is_authenticated = True

    def __str__(self):
        return f"<SimpleUser id={self.id} role={self.role} clinic_id={self.clinic_id}>"

class JWTAuthentication(BaseAuthentication):
    """
    Lê o header Authorization: Bearer <token>,
    valida com o JWTService e retorna (user, token).
    Em vez de buscar no modelo Django padrão, usa o UserRepoImpl para obter o usuário de domínio.
    """
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        parts = header.split()

        if not header or parts[0].lower() != "bearer" or len(parts) != 2:
            return None

        token = parts[1]
        try:
            payload = JWTService.decode_token(token)
        except jwt.PyJWTError as e:
            raise exceptions.AuthenticationFailed(f"Token inválido: {e}")  # noqa: B904

        user_id = payload.get("sub")
        if not user_id:
            raise exceptions.AuthenticationFailed("Token não contém o claim 'sub'.")

        # Busca o usuário no repositório de domínio
        user_repo = UserRepoImpl()
        domain_user = user_repo.find_by_id(user_id)
        if not domain_user:
            raise exceptions.AuthenticationFailed("Usuário não encontrado.")

        # Cria um usuário simples para compatibilidade com DRF
        simple_user = SimpleUser(
            id=domain_user.id,
            role=payload.get("role", getattr(domain_user, "role", None)),
            clinic_id=payload.get("clinic_id")
        )
        return (simple_user, token)


class CookieJWTAuthentication(BaseAuthentication):
    """
    Em vez de ler do header, busca o token em um cookie (settings.AUTH_COOKIE_NAME),
    valida com o JWTService e retorna (user, token).
    Também usa o UserRepoImpl para obter o usuário de domínio.
    """
    def authenticate(self, request):
        token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not token:
            return None

        try:
            payload = JWTService.decode_token(token)
        except jwt.PyJWTError as e:
            raise exceptions.AuthenticationFailed(f"Token inválido: {e}")  # noqa: B904

        user_id = payload.get("sub")
        if not user_id:
            raise exceptions.AuthenticationFailed("Token não contém o claim 'sub'.")

        # Busca o usuário no repositório de domínio
        user_repo = UserRepoImpl()
        domain_user = user_repo.find_by_id(user_id)
        if not domain_user:
            raise exceptions.AuthenticationFailed("Usuário não encontrado.")

        # Cria um usuário simples para compatibilidade com DRF
        simple_user = SimpleUser(
            id=domain_user.id,
            role=payload.get("role", getattr(domain_user, "role", None)),
            clinic_id=payload.get("clinic_id")
        )
        return (simple_user, token)
