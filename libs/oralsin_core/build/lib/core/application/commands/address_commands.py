from dataclasses import dataclass

from oralsin_core.core.application.cqrs import CommandDTO
from oralsin_core.core.application.dtos.address_dto import AddressDTO


@dataclass(frozen=True)
class CreateAddressCommand(CommandDTO):
    payload: AddressDTO

@dataclass(frozen=True)
class UpdateAddressCommand(CommandDTO):
    id: str
    payload: AddressDTO

@dataclass(frozen=True)
class DeleteAddressCommand(CommandDTO):
    id: str
