import logging
import os
import sys

import structlog


def configure_logging(
    level: str = "DEBUG",
    json_logs: bool = bool(os.getenv("JSON_LOGS", "")),
) -> None:
    """
    Configura structlog + logging:
     - Em `json_logs` ativa JSONRenderer para produção.
     - Caso contrário, usa ConsoleRenderer colorido para dev.
    Deve ser chamado ANTES de qualquer import que crie loggers.
    """

    # Pré-processors comuns a stdlib e structlog
    pre_chain = [
        structlog.contextvars.merge_contextvars,     # mantém trace_id, span_id etc.
        structlog.processors.add_log_level,          # level na raiz JSON / console
        structlog.processors.TimeStamper(fmt="iso"), # timestamp ISO-8601
    ]

    # Escolhe renderer final
    final_processor = structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(colors=True)
    from structlog.processors import CallsiteParameter, CallsiteParameterAdder

    # Configuração do structlog
    structlog.configure(
        processors=[
            *pre_chain,
            CallsiteParameterAdder(
                parameters=[
                    CallsiteParameter.PATHNAME, 
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                ]
            ),                                                     # mostra arquivo:linha
            structlog.processors.StackInfoRenderer(),              # stack info
            structlog.processors.format_exc_info,                  # trace de exceções
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,# ponte para stdlib
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level)
        ),
        cache_logger_on_first_use=True,
    )

    # Formatter para loggers stdlib
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=final_processor,
        foreign_pre_chain=pre_chain,
    )

    # Handler que vai pro stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Aplica no root logger
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Evita duplicar logs (Django, warnings, etc.)
    logging.captureWarnings(True)
