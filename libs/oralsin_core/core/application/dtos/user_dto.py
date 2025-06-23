
from typing import Literal

from pydantic import BaseModel, EmailStr


class CreateUserDTO(BaseModel):
    email: EmailStr
    password: str | None = None  
    password_hash: str | None = None 
    name: str
    role: Literal["admin", "clinic"]
    clinic_id: str | None = None
    
    class Config:
        from_attributes = True
        validate_by_name = True


class UpdateUserDTO(BaseModel):
    id: str
    role: Literal["admin", "clinic"]
    email: EmailStr | None = None
    password: str | None = None
    name: str | None = None
    clinic_name: str | None = None