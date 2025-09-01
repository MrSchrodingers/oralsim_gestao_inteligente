from __future__ import annotations

import re


def _only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _br_basic_normalize(d: str) -> str | None:
    """
    Fallback simples focado no Brasil:
      - remove prefixos '00' e '0'
      - aceita 10-11 dígitos como DDD+número
      - prefixa 55
      - rejeita <10
    """
    d = _only_digits(d)
    if not d:
        return None

    # internacional via '00'
    if d.startswith("00"):
        d = d[2:]

    # trunk '0' antes do DDD
    while d.startswith("0"):
        d = d[1:]

    # já tem CC Brasil
    if d.startswith("55") and 11 <= len(d) <= 15:  # noqa: PLR2004
        return d

    # DDD + número (10=fixo, 11=móvel)
    if len(d) in (10, 11):
        return "55" + d

    # já internacional sem '+', mantemos se 11–15
    if 11 <= len(d) <= 15:  # noqa: PLR2004
        return d

    return None

def normalize_phone(raw: str, default_region: str = "BR", digits_only: bool = True, with_plus: bool = False) -> str | None:  # noqa: PLR0911
    """
    Retorna número em formato internacional.
    - Preferência: lib 'phonenumbers' se disponível.
    - Fallback: heurística BR.
    - digits_only=True => '5543999999999' ; with_plus=True => '+5543999999999'
    """
    if not raw:
        return None

    try:
        import phonenumbers  # noqa: PLC0415
        from phonenumbers import NumberParseException  # noqa: PLC0415

        # Tenta parse com região default (BR)
        try:
            num = phonenumbers.parse(raw, default_region)
        except NumberParseException:
            # Tenta parse como internacional sem região
            raw_digits = _only_digits(raw)
            if raw_digits.startswith("00"):
                raw_digits = raw_digits[2:]
            try:
                num = phonenumbers.parse("+" + raw_digits)
            except NumberParseException:
                # último recurso: fallback BR
                d = _br_basic_normalize(raw)
                if not d:
                    return None
                return ("+" + d) if with_plus and not digits_only else d

        if not phonenumbers.is_possible_number(num):
            return None

        # Aceite um pouco mais amplo que 'valid' (WhatsApp costuma aceitar números 'possible')
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)  # +5543999...
        digits = _only_digits(e164)
        if not (10 <= len(digits) <= 15):  # noqa: PLR2004
            return None

        if with_plus and not digits_only:
            return e164  # com '+'
        return digits   # só dígitos

    except Exception:
        # Fallback sem dependência
        d = _br_basic_normalize(raw)
        return d if d else None
