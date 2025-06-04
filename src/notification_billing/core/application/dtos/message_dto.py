from pydantic import BaseModel


class MessageDTO(BaseModel):
    type: str
    content: str
    step: int
    clinic_id: str | None = None
    is_default: bool = False
