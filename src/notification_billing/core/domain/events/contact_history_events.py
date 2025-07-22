from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

Subscriber = Callable[["ContactHistoryCreated"], None]


@dataclass(slots=True, frozen=True)
class ContactHistoryCreated:
    """
    Domain‑event disparado sempre que um ContactHistory é persistido.
    Contém apenas o ID, evitando vazamento de dependências.
    """
    entity_id: str

    # ----- infraestrutura de pub/sub interna ------------------------------
    _subscribers: ClassVar[list[Subscriber]] = []

    @classmethod
    def subscribe(cls, fn: Subscriber) -> Subscriber:
        """Decorator para registrar *handlers* do evento."""
        cls._subscribers.append(fn)
        return fn

    @classmethod
    def emit(cls, entity_id: str) -> None:
        event = cls(entity_id=entity_id)
        for fn in cls._subscribers:
            try:
                fn(event)
            except Exception as exc:            # noqa: BLE001
                # logue e continue – evento não pode quebrar fluxo primário
                import structlog
                structlog.get_logger(__name__).error(
                    "domain_event_handler_failed",
                    handler=fn.__name__,
                    error=str(exc),
                )
