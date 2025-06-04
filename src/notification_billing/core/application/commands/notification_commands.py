from __future__ import annotations

import uuid
from dataclasses import dataclass

from notification_billing.core.application.cqrs import CommandDTO


@dataclass(frozen=True)
class SendManualNotificationCommand(CommandDTO):
    patient_id: uuid.UUID
    contract_id: uuid.UUID
    channel: str
    message_id: str

@dataclass(frozen=True)
class RunAutomatedNotificationsCommand(CommandDTO):
    clinic_id: str
    batch_size: int = 10
    only_pending: bool = True
    channel: str | None = None