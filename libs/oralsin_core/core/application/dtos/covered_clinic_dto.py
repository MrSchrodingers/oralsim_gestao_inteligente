from pydantic import BaseModel


class CoveredClinicCreateDTO(BaseModel):
    name: str