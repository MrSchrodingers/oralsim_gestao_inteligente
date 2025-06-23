from __future__ import annotations

from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO


@dataclass(frozen=True)
class RegisterCoverageClinicCommand(CommandDTO):
    clinic_name: str
    owner_name: str

@dataclass(frozen=True)
class LinkUserClinicCommand(CommandDTO):
    user_id: str
    clinic_id: str