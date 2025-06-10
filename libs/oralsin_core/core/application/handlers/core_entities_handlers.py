import uuid
from datetime import datetime

# Hash service
from oralsin_core.adapters.security.hash_service import HashService

# Commands
from oralsin_core.core.application.commands.address_commands import CreateAddressCommand, DeleteAddressCommand, UpdateAddressCommand
from oralsin_core.core.application.commands.clinic_commands import CreateClinicCommand, DeleteClinicCommand, UpdateClinicCommand
from oralsin_core.core.application.commands.clinic_data_commands import CreateClinicDataCommand, UpdateClinicDataCommand
from oralsin_core.core.application.commands.clinic_phone_commands import CreateClinicPhoneCommand, DeleteClinicPhoneCommand, UpdateClinicPhoneCommand
from oralsin_core.core.application.commands.coverage_commands import LinkUserClinicCommand
from oralsin_core.core.application.commands.covered_clinic_commands import RegisterCoveredClinicCommand
from oralsin_core.core.application.commands.patient_phone_commands import CreatePatientPhoneCommand, DeletePatientPhoneCommand, UpdatePatientPhoneCommand
from oralsin_core.core.application.commands.user_commands import CreateUserCommand, DeleteUserCommand, UpdateUserCommand
from oralsin_core.core.application.cqrs import CommandHandler

# Entities
from oralsin_core.core.domain.entities.address_entity import AddressEntity
from oralsin_core.core.domain.entities.clinic_data_entity import ClinicDataEntity
from oralsin_core.core.domain.entities.clinic_entity import ClinicEntity
from oralsin_core.core.domain.entities.clinic_phone_entity import ClinicPhoneEntity
from oralsin_core.core.domain.entities.covered_clinics import CoveredClinicEntity
from oralsin_core.core.domain.entities.patient_phone_entity import PatientPhoneEntity
from oralsin_core.core.domain.entities.user_clinic_entity import UserClinicEntity
from oralsin_core.core.domain.entities.user_entity import UserEntity

# Repositories
from oralsin_core.core.domain.repositories.address_repository import AddressRepository
from oralsin_core.core.domain.repositories.clinic_data_repository import ClinicDataRepository
from oralsin_core.core.domain.repositories.clinic_phone_repository import ClinicPhoneRepository
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.covered_clinic_repository import CoveredClinicRepository
from oralsin_core.core.domain.repositories.patient_phone_repository import PatientPhoneRepository
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
from oralsin_core.core.domain.repositories.user_repository import UserRepository

# ——— ADDRESS ——————————————————————————————————————————————

class CreateAddressHandler(CommandHandler[CreateAddressCommand]):
    def __init__(self, repo: AddressRepository):
        self.repo = repo

    def handle(self, command: CreateAddressCommand) -> AddressEntity:
        data = command.payload.dict()
        data['id'] = uuid.uuid4()
        entity = AddressEntity.from_dict(data)
        return self.repo.save(entity)

class UpdateAddressHandler(CommandHandler[UpdateAddressCommand]):
    def __init__(self, repo: AddressRepository):
        self.repo = repo

    def handle(self, command: UpdateAddressCommand) -> AddressEntity:
        data = command.payload.dict()
        data['id'] = command.id
        entity = AddressEntity.from_dict(data)
        return self.repo.save(entity)

class DeleteAddressHandler(CommandHandler[DeleteAddressCommand]):
    def __init__(self, repo: AddressRepository):
        self.repo = repo

    def handle(self, command: DeleteAddressCommand) -> None:
        self.repo.delete(command.id)


# ——— CLINIC ——————————————————————————————————————————————

class CreateClinicHandler(CommandHandler[CreateClinicCommand]):
    def __init__(self, repo: ClinicRepository):
        self.repo = repo

    def handle(self, command: CreateClinicCommand) -> ClinicEntity:
        data = command.payload.dict()
        data['id'] = uuid.uuid4()
        entity = ClinicEntity.from_dict(data)
        return self.repo.save(entity)

class UpdateClinicHandler(CommandHandler[UpdateClinicCommand]):
    def __init__(self, repo: ClinicRepository):
        self.repo = repo

    def handle(self, command: UpdateClinicCommand) -> ClinicEntity:
        data = command.payload.dict()
        data['id'] = command.id
        entity = ClinicEntity.from_dict(data)
        return self.repo.save(entity)

class DeleteClinicHandler(CommandHandler[DeleteClinicCommand]):
    def __init__(self, repo: ClinicRepository):
        self.repo = repo

    def handle(self, command: DeleteClinicCommand) -> None:
        self.repo.delete(command.id)


# ——— CLINIC DATA ——————————————————————————————————————————

class CreateClinicDataHandler(CommandHandler[CreateClinicDataCommand]):
    def __init__(self, repo: ClinicDataRepository):
        self.repo = repo

    def handle(self, command: CreateClinicDataCommand) -> ClinicDataEntity:
        data = command.payload.dict()
        entity = ClinicDataEntity.from_dict(data)
        return self.repo.save(entity)

class UpdateClinicDataHandler(CommandHandler[UpdateClinicDataCommand]):
    def __init__(self, repo: ClinicDataRepository):
        self.repo = repo

    def handle(self, command: UpdateClinicDataCommand) -> ClinicDataEntity:
        data = command.payload.dict()
        data['id'] = command.id
        entity = ClinicDataEntity.from_dict(data)
        return self.repo.save(entity)


# ——— CLINIC PHONE ——————————————————————————————————————————

class CreateClinicPhoneHandler(CommandHandler[CreateClinicPhoneCommand]):
    def __init__(self, repo: ClinicPhoneRepository):
        self.repo = repo

    def handle(self, command: CreateClinicPhoneCommand) -> ClinicPhoneEntity:
        data = command.payload.dict()
        entity = ClinicPhoneEntity.from_dict(data)
        return self.repo.save(entity)

class UpdateClinicPhoneHandler(CommandHandler[UpdateClinicPhoneCommand]):
    def __init__(self, repo: ClinicPhoneRepository):
        self.repo = repo

    def handle(self, command: UpdateClinicPhoneCommand) -> ClinicPhoneEntity:
        data = command.payload.dict()
        data['id'] = command.id
        entity = ClinicPhoneEntity.from_dict(data)
        return self.repo.save(entity)

class DeleteClinicPhoneHandler(CommandHandler[DeleteClinicPhoneCommand]):
    def __init__(self, repo: ClinicPhoneRepository):
        self.repo = repo

    def handle(self, command: DeleteClinicPhoneCommand) -> None:
        self.repo.delete(command.id)


# ——— PATIENT PHONE ——————————————————————————————————————————

class CreatePatientPhoneHandler(CommandHandler[CreatePatientPhoneCommand]):
    def __init__(self, repo: PatientPhoneRepository):
        self.repo = repo

    def handle(self, command: CreatePatientPhoneCommand) -> PatientPhoneEntity:
        data = command.payload.dict()
        entity = PatientPhoneEntity.from_dict(data)
        return self.repo.save(entity)

class UpdatePatientPhoneHandler(CommandHandler[UpdatePatientPhoneCommand]):
    def __init__(self, repo: PatientPhoneRepository):
        self.repo = repo

    def handle(self, command: UpdatePatientPhoneCommand) -> PatientPhoneEntity:
        data = command.payload.dict()
        data['id'] = command.id
        entity = PatientPhoneEntity.from_dict(data)
        return self.repo.save(entity)

class DeletePatientPhoneHandler(CommandHandler[DeletePatientPhoneCommand]):
    def __init__(self, repo: PatientPhoneRepository):
        self.repo = repo

    def handle(self, command: DeletePatientPhoneCommand) -> None:
        self.repo.delete(command.id)


# ——— USER ————————————————————————————————————————————————

class CreateUserHandler(CommandHandler[CreateUserCommand]):
    def __init__(self, repo: UserRepository, hash_service: HashService, user_clinic_repo: UserClinicRepository):
        self.repo = repo
        self.hash_service = hash_service
        self.user_clinic_repo = user_clinic_repo

    def handle(self, command: CreateUserCommand) -> UserEntity:
        data = command.payload.dict()
        data['id'] = uuid.uuid4()
        data['password_hash'] = self.hash_service.hash_password(data.pop('password'))
        clinic_id = data.pop("clinic_id", None)
        
        entity = UserEntity.from_dict(data)
        user = self.repo.save(entity)

        if user.role == "clinic" and clinic_id:
            self.user_clinic_repo.save(
                UserClinicEntity(
                    id=uuid.uuid4(),
                    user_id=str(user.id),
                    clinic_id=clinic_id,
                    linked_at=datetime.utcnow(),
                )
            )

        return user

class UpdateUserHandler(CommandHandler[UpdateUserCommand]):
    def __init__(self, repo: UserRepository, hash_service: HashService):
        self.repo = repo
        self.hash_service = hash_service

    def handle(self, command: UpdateUserCommand) -> UserEntity:
        data = command.payload.dict()
        data['id'] = command.payload.id
        if 'password' in data and data['password']:
            data['password_hash'] = self.hash_service.hash_password(data.pop('password'))
        entity = UserEntity.from_dict(data)
        return self.repo.save(entity)

class DeleteUserHandler(CommandHandler[DeleteUserCommand]):
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def handle(self, command: DeleteUserCommand) -> None:
        self.repo.delete(command.user_id)


# ——— COVERED CLINIC & LINK ——————————————————————————————————

class RegisterCoveredClinicHandler(CommandHandler[RegisterCoveredClinicCommand]):
    def __init__(self, repo: CoveredClinicRepository):
        self.repo = repo

    def handle(self, command: RegisterCoveredClinicCommand) -> CoveredClinicEntity:
        data = command.payload.dict()
        data['id'] = uuid.uuid4()
        entity = CoveredClinicEntity.from_dict(data)
        return self.repo.save(entity)

class LinkUserClinicHandler(CommandHandler[LinkUserClinicCommand]):
    def __init__(self, repo: UserClinicRepository):
        self.repo = repo

    def handle(self, command: LinkUserClinicCommand) -> UserClinicEntity:
        data = {
            'id': uuid.uuid4(),
            'user_id': command.user_id,
            'clinic_id': command.clinic_id,
            'linked_at': datetime.utcnow()
        }
        entity = UserClinicEntity.from_dict(data)
        return self.repo.save(entity)
