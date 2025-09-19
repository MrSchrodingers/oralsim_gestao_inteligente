from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class ContactPhoneDTO:
    """DTO simples para um telefone de contato."""
    phone_number: str
    phone_type: str

@dataclass(frozen=True)
class ContactInfoDTO:
    """
    Estrutura de dados unificada para o destinatário de uma notificação.
    Contém todos os dados necessários, seja do Paciente ou do Pagante.
    """
    name: str
    email: Optional[str]
    phones: List[ContactPhoneDTO]