from pydantic import BaseModel


class AddressDTO(BaseModel):
    street: str
    number: str
    complement: str | None = None
    neighborhood: str | None = None
    city: str
    state: str
    zip_code: str
