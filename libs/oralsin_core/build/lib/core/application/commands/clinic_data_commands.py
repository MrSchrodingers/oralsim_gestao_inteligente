from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.clinic_data_dto import ClinicDataDTO


@dataclass(frozen=True)
class CreateClinicDataCommand(CommandDTO):
    payload: ClinicDataDTO

@dataclass(frozen=True)
class UpdateClinicDataCommand(CommandDTO):
    id: str
    payload: ClinicDataDTO
