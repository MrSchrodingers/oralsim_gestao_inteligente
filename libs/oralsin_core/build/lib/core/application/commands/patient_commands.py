from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.patient_dto import RegisterPatientsDTO, UpdatePatientDTO


@dataclass(frozen=True)
class RegisterPatientsCommand(CommandDTO):
    payload: RegisterPatientsDTO

@dataclass(frozen=True)
class UpdatePatientCommand(CommandDTO):
    id: str
    payload: UpdatePatientDTO