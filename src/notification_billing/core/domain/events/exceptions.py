class NotificationError(Exception):
    """Classe base para todas as exceções de notificação."""
    pass

class PermanentNotificationError(NotificationError):
    """
    Representa um erro permanente que não deve ser retentado.
    Exemplos:
    - 4xx: Destinatário inválido (e-mail não existe, telefone formatado incorretamente).
    - API Key inválida.
    """
    pass

class TemporaryNotificationError(NotificationError):
    """
    Representa um erro temporário que pode ser resolvido com uma nova tentativa.
    Exemplos:
    - 5xx: Servidor do provedor de SMS/E-mail indisponível.
    - Falhas de rede, timeouts.
    """
    pass