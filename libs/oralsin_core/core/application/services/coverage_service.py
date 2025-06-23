from typing import Any

from oralsin_core.core.application.commands.coverage_commands import (
    LinkUserClinicCommand,
    RegisterCoverageClinicCommand,
)
from oralsin_core.core.application.cqrs import CommandBus, QueryBus
from oralsin_core.core.application.queries.coverage_queries import (
    ListCoveredClinicsQuery,
    ListUserClinicsQuery,
)


class CoverageService:
    def __init__(self, command_bus: CommandBus, query_bus: QueryBus) -> None:
        self.commands = command_bus
        self.queries = query_bus

    # ------------------------- API pública ------------------------- #
    def register_clinic(self, clinic_name: str, owner_name:str) -> None:
        """Registra/atualiza cobertura para a clínica cujo Nome == `clinic_name`."""
        self.commands.dispatch(
            RegisterCoverageClinicCommand(clinic_name=clinic_name, owner_name=owner_name)
        )

    def link_user(self, user_id: str, clinic_id: str) -> None:
        self.commands.dispatch(
            LinkUserClinicCommand(user_id=user_id, clinic_id=clinic_id)
        )

    def list_covered(self) -> list[Any]:
        return self.queries.dispatch(ListCoveredClinicsQuery())

    def list_user_clinics(self, user_id: str) -> list[Any]:
        return self.queries.dispatch(
            ListUserClinicsQuery(filtros={"user_id": user_id})
        )
