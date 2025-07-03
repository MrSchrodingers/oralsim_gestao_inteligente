from dataclasses import dataclass
from datetime import date

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.patient_dto import RegisterPatientsDTO


@dataclass(frozen=True)
class RegisterPatientsCommand:
    payload: RegisterPatientsDTO
    
@dataclass(frozen=True, slots=True)
class ResyncClinicCommand(CommandDTO):
    """
    Re-sincroniza dados de *uma* clínica Oralsin para manter
    pacientes, contratos e parcelas em dia.
    """
    oralsin_clinic_id: int
    initial_date:      date
    final_date:        date
    no_schedules:      bool = True 