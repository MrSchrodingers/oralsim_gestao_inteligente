"""
Fábrica de notifiers: devolve o provedor correto baseado no canal.
"""
import os
from functools import lru_cache
from typing import Literal

from notification_billing.adapters.notifiers.base import BaseNotifier
from notification_billing.adapters.notifiers.email.sendgrid import SendGridEmail
from notification_billing.adapters.notifiers.sms.assertiva import AssertivaSMS
from notification_billing.adapters.notifiers.whatsapp.debtapp import DebtAppWhatsapp


@lru_cache
def get_sms_notifier(key: str = "assertiva") -> BaseNotifier:
    return AssertivaSMS(
        auth_token=os.getenv("ASSERTIVA_AUTH_TOKEN", ""),
        base_url=os.getenv("ASSERTIVA_BASE_URL", ""),
        webhook_url=os.getenv("WEBHOOK_URL", ""),
    )


@lru_cache
def get_email_notifier(key: str = "sendgrid") -> BaseNotifier:
    return SendGridEmail(
        api_key=os.getenv("SENDGRID_API_KEY", ""),
        from_email=os.getenv("DEFAULT_FROM_EMAIL", ""),
    )


@lru_cache
def get_whatsapp_notifier(key: str = "debtapp") -> BaseNotifier:
    return DebtAppWhatsapp(
        apikey=os.getenv("DEBTAPP_WHATSAPP_API_KEY", ""),
        endpoint=os.getenv("DEBTAPP_WHATSAPP_ENDPOINT", ""),
    )


def get_notifier(channel: Literal["sms", "email", "whatsapp"]) -> BaseNotifier:
    """
    Retorna o provedor de notificação para o canal especificado.

    - 'sms' → AssertivaSMS
    - 'email' → SendGridEmail
    - 'whatsapp' → DebtAppWhatsapp
    """
    if channel == "sms":
        return get_sms_notifier()
    if channel == "email":
        return get_email_notifier()
    if channel == "whatsapp":
        return get_whatsapp_notifier()
    raise ValueError(f"Canal de notificação desconhecido: {channel}")
