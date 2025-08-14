from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.clinic_phone_dto import ClinicPhoneDTO


@dataclass(frozen=True)
class CreateClinicPhoneCommand(CommandDTO):
    payload: ClinicPhoneDTO

@dataclass(frozen=True)
class UpdateClinicPhoneCommand(CommandDTO):
    id: str
    payload: ClinicPhoneDTO

@dataclass(frozen=True)
class DeleteClinicPhoneCommand(CommandDTO):
    id: str
