from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from oralsin_core.adapters.config.composition_root import setup_di_container_from_settings
from oralsin_core.core.application.commands.user_commands import CreateUserCommand
from oralsin_core.core.application.dtos.user_dto import CreateUserDTO


class Command(BaseCommand):
    """
    Cria ou atualiza o superusuário administrador do sistema.
    Este comando é idempotente e seguro para ser executado múltiplas vezes.
    """
    help = "Cria ou atualiza o usuário administrador (super_admin)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--email", type=str, required=True, help="Email de login para o superusuário.")
        parser.add_argument("--password", type=str, required=True, help="Senha para o superusuário.")
        parser.add_argument("--name", type=str, default="Super Admin", help="Nome do superusuário.")

    def handle(self, *args: Any, **opt: Any) -> None:
        self.stdout.write(self.style.NOTICE("--- Iniciando criação do usuário Admin ---"))
        
        container = setup_di_container_from_settings(None)
        cmd_bus = container.command_bus()

        payload = CreateUserDTO(
            email=opt["email"],
            password=opt["password"],
            name=opt["name"],
            role="admin",  # Garante que o usuário sempre terá o papel de admin
        )
        
        # O handler de CreateUserCommand já deve ser idempotente (usando get_or_create)
        try:
            result = cmd_bus.dispatch(CreateUserCommand(payload=payload))
            self.stdout.write(self.style.SUCCESS(
                f"✅ Usuário Admin '{result.email}' criado com sucesso. ID: {result.id}"
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"❌ Falha inesperada ao criar usuário Admin '{opt['email']}': {e}"
            ))