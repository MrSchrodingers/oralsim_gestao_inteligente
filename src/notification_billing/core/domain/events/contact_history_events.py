from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ContactHistoryCreated:
    """
    Domain-event disparado sempre que um ContactHistory é persistido.
    Contém apenas o ID, evitando vazamento de dependências.
    """
    entity_id: str