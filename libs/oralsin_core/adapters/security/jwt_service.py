from datetime import datetime, timedelta

import jwt

from config import settings


class JWTService:
    """
    Serviço de criação e validação de tokens JWT.
    """

    @staticmethod
    def create_token(
        subject: str,
        expires_in: int,
        role: str,
        clinic_id: str | None = None,
    ) -> str:
        """Gera um token JWT com claim 'sub', role e expiração."""
        
        now = datetime.utcnow()
        payload = {
            "sub": str(subject), 
            "role": role,
            "iat": now,
            "exp": now + timedelta(seconds=int(expires_in)),
        }
        if clinic_id is not None:
            payload["clinic_id"] = clinic_id
            
        token = jwt.encode(
            payload,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        # PyJWT retorna str no v2+
        return token

    @staticmethod
    def decode_token(token: str) -> dict:
        """
        Decodifica e valida o token JWT, retornando o payload.
        Lança jwt.PyJWTError se inválido ou expirado.
        """
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
