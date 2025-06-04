
from typing import Literal

from pydantic import BaseModel, EmailStr


class CreateUserDTO(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "clinic"]
    clinic_name: str | None = None


class UpdateUserDTO(BaseModel):
    id: str
    role: Literal["admin", "clinic"]
    email: EmailStr | None = None
    password: str | None = None
    name: str | None = None
    clinic_name: str | None = None