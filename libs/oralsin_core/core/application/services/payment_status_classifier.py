import re
import unicodedata

from django.db import transaction

from plugins.django_interface.models import PaymentStatus

_BANK_OR_GATEWAY_RX = re.compile(
    r"\b("
    r"banco\b|pagseguro|cora\b|cielo|stone|rede|sicredi|unicred"
    r")",
    re.I,
)
_NEGATIVE = {
    "nao compensado", "não compensado", "estorno solicitado", "custodia interna",
    "status inicial", "devolver ao paciente", "enviado ao financeiro",
}

_POSITIVE = {
    "compensado", "caixa clinica", "negociacao concluida",
    "repassado", "antecipado", "estorno concluido",
}

def _norm(txt: str) -> str:
    return unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower().strip()

def is_paid_status(raw_status: str) -> bool:
    norm = _norm(raw_status or "")
    if not norm:
        return False

    # ── 1) catálogo
    if (ps := PaymentStatus.objects.filter(normalized=norm).first()):
        return ps.is_paid

    # ── 2) heurística
    has_gateway_kw = bool(_BANK_OR_GATEWAY_RX.search(norm))   
    is_paid = (norm in _POSITIVE) or (has_gateway_kw and norm not in _NEGATIVE)
    kind = "gateway" if has_gateway_kw else (
        "positive" if norm in _POSITIVE
        else "negative" if norm in _NEGATIVE
        else "unknown"
    )
    
    with transaction.atomic():
        obj, _ = PaymentStatus.objects.update_or_create(
        normalized=norm,
        defaults=dict(
            raw_status=raw_status,  # armazena última “grafia” recebida
            is_paid=is_paid,
            kind=kind,
        ),
    )
    return obj.is_paid
