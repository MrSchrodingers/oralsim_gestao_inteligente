from collections.abc import Callable

import structlog

from oralsin_core.core.domain.events.events import DomainEvent

logger = structlog.get_logger(__name__)

class EventDispatcher:
    """
    Dispatcher de eventos de domínio.
    """
    def __init__(self) -> None:
        self._subs: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = {}

    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        self._subs.setdefault(event_type, []).append(handler)
        logger.debug(
            "event.subscribed",
            event_type=event_type.__name__,
            handler_name=handler.__name__,
        )

    def dispatch(self, event: DomainEvent) -> None:
        handlers = self._subs.get(type(event), [])
        logger.info(
            "event.dispatch",
            event_name=type(event).__name__,
            listeners=len(handlers),
        )
        for h in handlers:
            try:
                h(event)
            except Exception as e:
                logger.error(
                    "event.handler_error",
                    event_name=type(event).__name__,
                    handler_name=h.__name__,
                    error=str(e),
                    exc_info=True,
                )
