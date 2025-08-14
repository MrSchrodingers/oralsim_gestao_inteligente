import bcrypt


class HashService:
    """
    Serviço de hash de senhas usando bcrypt.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        # Gera salt e faz o hash da senha
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        """
        Verifica se a senha corresponde ao hash armazenado.
        """
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False