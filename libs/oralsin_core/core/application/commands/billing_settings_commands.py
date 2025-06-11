from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO


@dataclass(frozen=True, slots=True)
class UpdateBillingSettingsCommand(CommandDTO):
    clinic_id: str
    min_days_overdue: int