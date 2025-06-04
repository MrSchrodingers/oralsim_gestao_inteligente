from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

import structlog

from notification_billing.core.domain.events.events import DomainEvent
from notification_billing.core.domain.services.event_dispatcher import EventDispatcher

# ───────────────────────────────────────────────
# CQRS Genérico com Suporte a Paginação e Log de Performance
# ───────────────────────────────────────────────

# Type variables
C = TypeVar('C')  # Command type
Q = TypeVar('Q')  # Query filtros type
R = TypeVar('R')  # Query result type
T = TypeVar('T')  # PagedResult item type

# Logger
logger = structlog.get_logger(__name__)

# ───────────────────────────────────────────────
# DTOs
# ───────────────────────────────────────────────
@dataclass(frozen=True)
class CommandDTO:
    """Base para todos comandos de escrita (Create/Update/Delete)."""
    pass

@dataclass(frozen=True)
class QueryDTO(Generic[Q]):
    """Base para consultas de leitura."""
    filtros: Q

@dataclass(frozen=True)
class PaginatedQueryDTO(Generic[Q]):
    """Consulta paginada: filtros + paginação."""
    filtros: Q
    page: int = 1
    page_size: int = 50

@dataclass(frozen=True)
class PagedResult(Generic[T]):
    """Resultado paginado padrão."""
    items: Sequence[T]
    total: int
    page: int
    page_size: int
    total_pages: int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'total_pages', math.ceil(self.total / self.page_size) if self.page_size else 0)

# ───────────────────────────────────────────────
# Handlers Protocols
# ───────────────────────────────────────────────
class CommandHandler(Protocol, Generic[C]):
    def handle(self, command: C) -> Any:
        """Processa um comando e aplica mudanças de estado."""
        ...

class QueryHandler(Protocol, Generic[Q, R]):
    def handle(self, query: QueryDTO[Q]) -> R:
        """Processa uma consulta e retorna um resultado."""
        ...

# ───────────────────────────────────────────────
# Buses com Logging e Métricas
# ───────────────────────────────────────────────
class CommandBus:
    """Dispatcher de comandos com medição de performance."""
    def __init__(self) -> None:
        self._handlers: dict[type, CommandHandler] = {}

    def register(self, command_type: type[C], handler: CommandHandler[C]) -> None:
        self._handlers[command_type] = handler
        logger.debug("CommandHandler registrado", command=command_type.__name__)

    def dispatch(self, command: C) -> Any:
        handler = self._handlers.get(type(command))
        if not handler:
            raise ValueError(f"Nenhum handler para comando: {type(command).__name__}")
        start = time.time()
        logger.info("Executando comando", command=type(command).__name__)
        result = handler.handle(command)
        elapsed = time.time() - start
        logger.info("Comando executado", command=type(command).__name__, duration=f"{elapsed:.3f}s")
        return result

class QueryBus:
    """Dispatcher de queries com medição e suporte à paginação."""
    def __init__(self) -> None:
        self._handlers: dict[type, QueryHandler] = {}

    def register(self, query_type: type[QueryDTO], handler: QueryHandler[Any, Any]) -> None:
        self._handlers[query_type] = handler
        logger.debug("QueryHandler registrado", query=query_type.__name__)

    def dispatch(self, query: QueryDTO[Any]) -> Any:
        handler = self._handlers.get(type(query))
        if not handler:
            raise ValueError(f"Nenhum handler para query: {type(query).__name__}")
        start = time.time()
        logger.info("Executando query", query=type(query).__name__)
        result = handler.handle(query)
        elapsed = time.time() - start
        logger.info("Query executada", query=type(query).__name__, duration=f"{elapsed:.3f}s")
        return result

# ───────────────────────────────────────────────
# Service de Alto Nível
# ───────────────────────────────────────────────
class BaseService:
    """Orquestra execução de comandos e queries via buses."""
    def __init__(self, command_bus: CommandBus, query_bus: QueryBus) -> None:
        self.commands = command_bus
        self.queries = query_bus

    def execute(self, command: CommandDTO) -> Any:
        return self.commands.dispatch(command)

    def query(self, query: QueryDTO[Any]) -> Any:
        return self.queries.dispatch(query)

    def paginate(self, paginated_query: PaginatedQueryDTO[Any]) -> PagedResult[Any]:
        result = self.queries.dispatch(paginated_query)
        if not isinstance(result, PagedResult):
            raise TypeError(f"Esperado PagedResult, obteve {type(result).__name__}")
        return result

class CommandBusImpl(CommandBus):
    """
    Implementação do CommandBus que usa o dispatcher de eventos
    para casos em que handlers possam lançar DomainEvents.
    """
    def __init__(self, dispatcher: EventDispatcher):
        super().__init__()
        self.dispatcher = dispatcher
        self._dispatcher = dispatcher

    def dispatch(self, command: Any) -> Any:
        # chama o dispatch “pai” para executar handler.handle(...)
        result = super().dispatch(command)

        # se o resultado for uma coroutine, aguardamos sua execução
        if asyncio.iscoroutine(result):
            # Executa a coroutine até a conclusão no loop padrão
            result = asyncio.run(result)

        # Agora processamos DomainEvent(s) como antes
        if isinstance(result, DomainEvent):
            self.dispatcher.dispatch(result)
        elif hasattr(result, "__iter__") and not isinstance(result, str | bytes):
            for evt in result:
                self.dispatcher.dispatch(evt)

        return result


class QueryBusImpl(QueryBus):
    """
    Implementação padrão de QueryBus (herda toda a lógica de QueryBus).
    """
    # não exige nada além do já definido em QueryBus
    pass