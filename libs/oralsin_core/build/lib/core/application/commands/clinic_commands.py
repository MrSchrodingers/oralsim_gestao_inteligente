from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.clinic_dto import ClinicDTO


@dataclass(frozen=True)
class CreateClinicCommand(CommandDTO):
    payload: ClinicDTO

@dataclass(frozen=True)
class UpdateClinicCommand(CommandDTO):
    id: str
    payload: ClinicDTO

@dataclass(frozen=True)
class DeleteClinicCommand(CommandDTO):
    id: str
