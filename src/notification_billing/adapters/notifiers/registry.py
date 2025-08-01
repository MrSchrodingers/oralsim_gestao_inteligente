"""
Fábrica de notifiers: devolve o provedor correto baseado no canal.
"""
import os
from functools import lru_cache
from typing import Literal

from notification_billing.adapters.notifiers.base import BaseNotifier
from notification_billing.adapters.notifiers.email.microsoft_graph import MicrosoftGraphEmail
from notification_billing.adapters.notifiers.letter.letter_notifier import LetterNotifier
from notification_billing.adapters.notifiers.sms.assertiva import AssertivaSMS
from notification_billing.adapters.notifiers.whatsapp.debtapp import DebtAppWhatsapp


@lru_cache
def get_sms_notifier(key: str = "assertiva") -> BaseNotifier:
    return AssertivaSMS(
        auth_token=os.getenv("ASSERTIVA_AUTH_TOKEN"),
        base_url=os.getenv("ASSERTIVA_BASE_URL")
    )


@lru_cache
def get_email_notifier(key: str = "msgraph") -> BaseNotifier:
    return MicrosoftGraphEmail(
        tenant_id=os.getenv("MS_TENANT_ID"),
        client_id=os.getenv("MS_CLIENT_ID"),
        client_secret=os.getenv("MS_CLIENT_SECRET"),
        from_email=os.getenv("DEFAULT_FROM_EMAIL"),
    )


@lru_cache
def get_whatsapp_notifier(key: str = "debtapp") -> BaseNotifier:
    return DebtAppWhatsapp(
        apikey=os.getenv("DEBTAPP_WHATSAPP_API_KEY"),
        endpoint=os.getenv("DEBTAPP_WHATSAPP_ENDPOINT"),
    )

@lru_cache
def get_letter_notifier() -> BaseNotifier:
    # Assume que o template está na raiz do projeto.
    template_path = "ModeloCartaAmigavel.docx"
    email_sender = get_email_notifier()
    return LetterNotifier(template_path, email_sender)

def get_notifier(channel: Literal["sms", "email", "whatsapp", "letter"]) -> BaseNotifier:
    """
    Retorna o provedor de notificação para o canal especificado.

    - 'sms' → AssertivaSMS
    - 'email' → MS Graph
    - 'whatsapp' → DebtAppWhatsapp
    - 'letter' → MS Graph (fixo)
    """
    if channel == "sms":
        return get_sms_notifier()
    if channel == "email":
        return get_email_notifier()
    if channel == "whatsapp":
        return get_whatsapp_notifier()
    if channel == "letter": 
        return get_letter_notifier()
    raise ValueError(f"Canal de notificação desconhecido: {channel}")
