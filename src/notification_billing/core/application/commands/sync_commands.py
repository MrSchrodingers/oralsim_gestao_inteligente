from __future__ import annotations

from dataclasses import dataclass

from notification_billing.core.application.cqrs import CommandDTO


@dataclass(frozen=True)
class ScheduleNextContactsCommand(CommandDTO):
    contact_schedule_id: str
    
@dataclass(frozen=True)
class BulkScheduleContactsCommand(CommandDTO):
    clinic_id: int
    min_days_overdue: int = 1  

@dataclass(frozen=True)
class RecordContactOutcomeCommand(CommandDTO):
    history_id: str
    feedback_status: str
    observation: str