from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.patient_phone_dto import PatientPhoneDTO


@dataclass(frozen=True)
class CreatePatientPhoneCommand(CommandDTO):
    payload: PatientPhoneDTO

@dataclass(frozen=True)
class UpdatePatientPhoneCommand(CommandDTO):
    id: str
    payload: PatientPhoneDTO

@dataclass(frozen=True)
class DeletePatientPhoneCommand(CommandDTO):
    id: str
