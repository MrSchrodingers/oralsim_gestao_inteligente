#!/usr/bin/env python
import os
import sys

from config.structlog_config import configure_logging

configure_logging(level="DEBUG")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

def main():
    """Função principal para a execução das tasks de gerenciamento do Django."""
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar Django. Verifique se está instalado e no seu PYTHONPATH."
        ) from exc

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
