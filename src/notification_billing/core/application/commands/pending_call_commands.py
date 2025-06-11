from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO


@dataclass(frozen=True, slots=True)
class SetPendingCallDoneCommand(CommandDTO):
    """Marca a PendingCall como DONE ou FAILED."""
    call_id: str
    success: bool
    notes: str | None = None
    user_id: str | None = None  # para auditoria opcional