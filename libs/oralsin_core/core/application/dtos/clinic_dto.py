from pydantic import BaseModel


class ClinicDTO(BaseModel):
    name: str
    cnpj: str | None = None
