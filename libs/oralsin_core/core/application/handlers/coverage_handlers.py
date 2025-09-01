from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import structlog

from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
from oralsin_core.adapters.context.request_context import get_current_request
from oralsin_core.core.application.commands.coverage_commands import (
    LinkUserClinicCommand,
    RegisterCoverageClinicCommand,
)
from oralsin_core.core.application.cqrs import (
    CommandHandler,
    PaginatedQueryDTO,
    QueryHandler,
)
from oralsin_core.core.application.dtos.oralsin_dtos import ClinicsQueryDTO
from oralsin_core.core.application.queries.coverage_queries import (
    ListCoveredClinicsQuery,
    ListUserClinicsQuery,
)
from oralsin_core.core.domain.entities.clinic_entity import ClinicEntity
from oralsin_core.core.domain.entities.clinic_phone_entity import ClinicPhoneEntity
from oralsin_core.core.domain.entities.covered_clinics import CoveredClinicEntity
from oralsin_core.core.domain.entities.user_clinic_entity import UserClinicEntity
from oralsin_core.core.domain.events.events import (
    CoveredClinicRegisteredEvent,
    UserClinicLinkedEvent,
)
from oralsin_core.core.domain.mappers.oralsin_payload_mapper import OralsinPayloadMapper
from oralsin_core.core.domain.repositories.address_repository import AddressRepository
from oralsin_core.core.domain.repositories.clinic_data_repository import ClinicDataRepository
from oralsin_core.core.domain.repositories.clinic_phone_repository import ClinicPhoneRepository
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.covered_clinic_repository import CoveredClinicRepository
from oralsin_core.core.domain.repositories.user_clinic_repository import UserClinicRepository
from oralsin_core.core.domain.services.event_dispatcher import EventDispatcher

logger = structlog.get_logger(__name__)


# ╭──────────────────────────────────────────────╮
# │ 1. Registrar / atualizar cobertura           │
# ╰──────────────────────────────────────────────╯
class RegisterCoverageClinicHandler(
    CommandHandler[RegisterCoverageClinicCommand]
):
    """
    • Busca a clínica por **NOME** na Oralsin  
    • Persiste Clinic, CoveredClinic, ClinicData, ClinicPhone e Address  
    • Dispara `SyncInadimplenciaCommand` inicial (data = hoje)
    """

    def __init__(  # noqa: D401, PLR0913
        self,
        api_client: OralsinAPIClient,
        clinic_repo: ClinicRepository,
        covered_repo: CoveredClinicRepository,
        clinic_data_repo: ClinicDataRepository,
        clinic_phone_repo: ClinicPhoneRepository,
        address_repo: AddressRepository,
        mapper: OralsinPayloadMapper,
        command_bus: Any,
        dispatcher: EventDispatcher,
    ) -> None:
        self.api = api_client
        self.clinic_repo = clinic_repo
        self.covered_repo = covered_repo
        self.clinic_data_repo = clinic_data_repo
        self.clinic_phone_repo = clinic_phone_repo
        self.address_repo = address_repo
        self.mapper = mapper
        self.bus = command_bus
        self.dispatcher = dispatcher

    # ------------------------------------------------------------------ handle -----
    def handle(self, command: RegisterCoverageClinicCommand) -> CoveredClinicEntity:
        name = command.clinic_name.strip()
        logger.debug("Registrando cobertura", clinic_name=name)

        # 1️⃣  consulta na Oralsin (search = nome exato)
        page = self.api.get_clinics(
            PaginatedQueryDTO[ClinicsQueryDTO](
                filtros=ClinicsQueryDTO(search=name, ativo=1),
                page=1,
                page_size=1,
            )
        )
        if not page.items:
            raise ValueError(f"Clínica '{name}' não encontrada na Oralsin")

        dto = page.items[0]  # sempre 1

        # 2️⃣  Clinic (up-sert básico)
        clinic_ent = ClinicEntity(
            id=uuid.uuid4(),
            oralsin_clinic_id=dto.idClinica,
            name=dto.nomeClinica,
            cnpj=dto.cnpj or "",
            owner_name=command.owner_name
        )
        saved_clinic = self.clinic_repo.save(clinic_ent)

        # 3️⃣  Address  ➜  ClinicData (sempre gravar o Address primeiro)
        clinic_data_ent = self.mapper.map_clinic_data(dto, saved_clinic.id)
        if clinic_data_ent.address:
            saved_addr = self.address_repo.save(clinic_data_ent.address)
            # atualiza a entidade para referenciar o ID real
            clinic_data_ent.address = saved_addr
        # agora sim gravamos o ClinicData com address_id consistente
        self.clinic_data_repo.save(clinic_data_ent)

        # 4️⃣  Telefones
        for phone in self.mapper.map_clinic_phones(dto, saved_clinic.id):
            self.clinic_phone_repo.save(phone)
        # 4.1️⃣  Telefone de contato vindo do comando (se houver)
        if getattr(command, "contact_phone", None):
            self.clinic_phone_repo.save_contact_phone(
                ClinicPhoneEntity(
                    id=uuid.uuid4(),
                    clinic_id=saved_clinic.id,
                    phone_number=command.contact_phone,
                    phone_type="contact",
                ),
                contact_phone=command.contact_phone,
            )
    
        # 5️⃣  CoveredClinic
        covered_ent = self.mapper.map_covered_clinic(dto, saved_clinic.id)
        saved_covered = self.covered_repo.save(covered_ent)

        self.dispatcher.dispatch(
            CoveredClinicRegisteredEvent(
                clinic_id=saved_covered.id,
                oralsin_clinic_id=saved_covered.oralsin_clinic_id,
                name=saved_covered.name,
            )
        )

        return saved_covered


# ╭──────────────────────────────────────────────╮
# │ 2. Link user ↔ clinic                        │
# ╰──────────────────────────────────────────────╯
class LinkUserClinicHandler(CommandHandler[LinkUserClinicCommand]):
    def __init__(
        self,
        user_clinic_repo: UserClinicRepository,
        dispatcher: EventDispatcher,
    ) -> None:
        self.repo = user_clinic_repo
        self.dispatcher = dispatcher

    def handle(self, command: LinkUserClinicCommand) -> UserClinicEntity:
        link = UserClinicEntity(
            id=uuid.uuid4(),
            user_id=command.user_id,
            clinic_id=command.clinic_id,
            linked_at=datetime.utcnow(),
        )
        saved = self.repo.save(link)
        self.dispatcher.dispatch(
            UserClinicLinkedEvent(user_id=saved.user_id, clinic_id=saved.clinic_id)
        )
        return saved


# ╭──────────────────────────────────────────────╮
# │ 3. Listagens simples                         │
# ╰──────────────────────────────────────────────╯
class ListCoveredClinicsHandler(
    QueryHandler[ListCoveredClinicsQuery, Sequence[CoveredClinicEntity]]
):
    def __init__(self, covered_repo: CoveredClinicRepository) -> None:
        self.repo = covered_repo

    def handle(self, query: ListCoveredClinicsQuery) -> list[CoveredClinicEntity]:
        req = get_current_request()
        if req and getattr(req.user, "role", None) == "clinic":
            clinic_id = getattr(req.user, "clinic_id", None)
            if clinic_id:
                return [c for c in self.repo.list_all() if str(c.id) == str(clinic_id)]
        return self.repo.list_all()


class ListUserClinicsHandler(
    QueryHandler[ListUserClinicsQuery, Sequence[UserClinicEntity]]
):
    def __init__(self, user_clinic_repo: UserClinicRepository) -> None:
        self.repo = user_clinic_repo

    def handle(self, query: ListUserClinicsQuery) -> list[UserClinicEntity]:
        clinic_id = query.filtros.get("clinic_id")
        req = get_current_request()
        if not clinic_id and req and getattr(req.user, "role", None) == "clinic":
            clinic_id = getattr(req.user, "clinic_id", None)
        items = self.repo.find_by_user(query.filtros["user_id"])
        if clinic_id:
            items = [i for i in items if str(i.clinic_id) == str(clinic_id)]
        return items
