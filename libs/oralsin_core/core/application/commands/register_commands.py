from dataclasses import dataclass

from oralsin_core.core.application.dtos.patient_dto import RegisterPatientsDTO


@dataclass(frozen=True)
class RegisterPatientsCommand:
    payload: RegisterPatientsDTO