from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from oralsin_core.core.application.cqrs import CommandDTO


@dataclass(frozen=True)
class SyncInadimplenciaCommand(CommandDTO):
    oralsin_clinic_id: int
    data_inicio: date
    data_fim: date
    resync: bool = False
