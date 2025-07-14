from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UpdatePipedriveDealCommand:
    """
    Atualiza um Deal existente quando:
      • muda o valor devido OU
      • paciente deixa de ter cobrança ativa (do_billing=False ou dívida quitada)
    """
    collection_case_id: UUID
