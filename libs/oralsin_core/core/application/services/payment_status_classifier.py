import re
import unicodedata

from django.db import transaction

from plugins.django_interface.models import PaymentStatus

_BANK_OR_GATEWAY_RX = re.compile(
    r"\b("
    r"banco\b|pagseguro|cora\b|cielo|stone|rede|sicredi|unicred|bradesco|inter|brasil|uniprime"
    r")",
    re.I,
)

# Lista expandida com todos os status conhecidos que indicam NÃO PAGAMENTO.
_NEGATIVE = {
    "nao compensado", "não compensado", "estorno solicitado", "custodia interna",
    "status inicial", "devolver ao paciente", "enviado ao financeiro", 
    "devolvido ao paciente", "devolvido ao comercial - conf. irregular", "agendado",
}

# Lista expandida com todos os status conhecidos que indicam PAGAMENTO.
_POSITIVE = {
    "compensado", "caixa clinica", "negociacao concluida",
    "repassado", "antecipado", "estorno concluido", "pagseguro", "pagseguro 2",
    "conferencia realizada - financeiro", "conferencia realizada - comercial",
    "baixado",
}

def _norm(txt: str) -> str:
    """Normaliza o texto para comparação: minúsculas, sem acentos e sem espaços extras."""
    if not txt:
        return ""
    return unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower().strip()

def is_paid_status(raw_status: str) -> bool:
    norm = _norm(raw_status)
    if not norm:
        return False

    # --- 1) Catálogo (Fonte de Verdade Primária) ---
    if (ps := PaymentStatus.objects.filter(normalized=norm).first()):
        return ps.is_paid

    # --- 2) Heurística (Rede de Segurança Aprimorada) ---
    has_gateway_kw = bool(_BANK_OR_GATEWAY_RX.search(norm))
    
    # A lógica foi levemente ajustada para ser mais explícita.
    is_paid = False
    if norm in _POSITIVE:
        is_paid = True
    elif has_gateway_kw and norm not in _NEGATIVE:
        # Se contém nome de banco/gateway e NÃO está na lista negativa, é pago.
        is_paid = True

    kind = "gateway" if has_gateway_kw else (
        "positive" if norm in _POSITIVE
        else "negative" if norm in _NEGATIVE
        else "unknown"
    )
    
    # --- 3) Autoaprendizagem ---
    with transaction.atomic():
        obj, _ = PaymentStatus.objects.update_or_create(
            normalized=norm,
            defaults=dict(
                raw_status=raw_status,
                is_paid=is_paid,
                kind=kind,
            ),
        )
    return obj.is_paid