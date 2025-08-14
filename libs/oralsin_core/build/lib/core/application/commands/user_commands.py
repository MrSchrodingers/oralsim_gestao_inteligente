from dataclasses import dataclass

from oralsin_core.core.application.dtos.user_dto import CreateUserDTO, UpdateUserDTO


@dataclass(frozen=True)
class CreateUserCommand:
    payload: CreateUserDTO


@dataclass(frozen=True)
class UpdateUserCommand:
    payload: UpdateUserDTO


@dataclass(frozen=True)
class DeleteUserCommand:
    user_id: str