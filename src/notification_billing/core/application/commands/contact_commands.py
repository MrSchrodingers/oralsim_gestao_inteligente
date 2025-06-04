from __future__ import annotations

import uuid
from dataclasses import dataclass

from notification_billing.core.application.cqrs import CommandDTO


@dataclass(frozen=True)
class AdvanceContactStepCommand(CommandDTO):
    schedule_id: uuid.UUID

@dataclass(frozen=True)
class RecordContactSentCommand(CommandDTO):
    schedule_id: uuid.UUID
    success: bool
    feedback_status: str | None = None
    observation: str | None = None