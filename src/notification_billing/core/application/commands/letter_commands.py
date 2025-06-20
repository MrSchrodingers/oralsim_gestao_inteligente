from __future__ import annotations

import dataclasses

from notification_billing.core.application.cqrs import CommandDTO


@dataclasses.dataclass(frozen=True)
class SendPendingLettersCommand(CommandDTO):
    """
    Comando para buscar todas as cartas pendentes de uma clínica,
    gerá-las e enviar em um único e-mail em lote.
    """
    clinic_id: str