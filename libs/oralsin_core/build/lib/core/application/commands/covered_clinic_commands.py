from dataclasses import dataclass

from oralsin_core.core.application.dtos.covered_clinic_dto import CoveredClinicCreateDTO


@dataclass(frozen=True)
class RegisterCoveredClinicCommand:
    payload: CoveredClinicCreateDTO
