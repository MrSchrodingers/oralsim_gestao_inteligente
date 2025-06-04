import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """
    Configure structlog + logging em JSON no stdout.

    Chame esta função **ANTES** de qualquer import que crie loggers
    (idealmente no `settings.py` ou logo no início de `manage.py` / `wsgi.py`).
    """
    # ── Pré-processors que rodam só para loggers stdlib ────────────── #
    pre_chain = [
        structlog.contextvars.merge_contextvars,     # mantém trace_id, etc.
        structlog.processors.add_log_level,          # level na raiz JSON
        structlog.processors.TimeStamper(fmt="iso"), # timestamp ISO-8601
    ]

    # ── Config do structlog para BoundedLogger default ─────────────── #
    structlog.configure(
        processors=[
            *pre_chain,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level)
        ),
        cache_logger_on_first_use=True,
    )

    # ── Formatter único para stdlib → chama pre_chain + JSONRenderer ─ #
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=pre_chain,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # ── Root logger pega o handler; limpa handlers default do Django ─ #
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Evita que Django duplique (propagate=True em app loggers)
    logging.captureWarnings(True)
