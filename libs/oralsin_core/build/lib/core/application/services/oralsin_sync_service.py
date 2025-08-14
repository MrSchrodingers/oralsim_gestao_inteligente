from collections.abc import Sequence
from datetime import date
from typing import Any

from oralsin_core.core.application.commands.sync_commands import (
    SyncInadimplenciaCommand,
)
from oralsin_core.core.application.cqrs import CommandBus, QueryBus
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinPacienteDTO
from oralsin_core.core.application.queries.overdue_queries import ListPatientsInDebtQuery


class OralsinSyncService:
    """
    Serviço de alto nível para orquestrar sincronização de inadimplência,
    agendamento de contatos e registro de feedback.
    """

    def __init__(
        self,
        command_bus: CommandBus,
        query_bus: QueryBus,
    ) -> None:
        self._commands = command_bus
        self._queries = query_bus

    def full_sync(
        self,
        clinic_id: int,
        data_inicio: date,
        data_fim: date,
        no_schedules=False,
        resync: bool = False
    ) -> None:
        """Dispara sincronização completa de inadimplência para uma clínica."""
        cmd = SyncInadimplenciaCommand(
            oralsin_clinic_id   =clinic_id,
            data_inicio         =data_inicio,
            data_fim            =data_fim,
            resync              = resync,
        )
        self._commands.dispatch(cmd)

    def list_overdue_patients(
        self,
        clinic_id: int,
        min_days_overdue: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Any:
        """Retorna pacientes em atraso paginados."""
        query = ListPatientsInDebtQuery(
            filtros={
                "clinic_id": clinic_id,
                "min_overdue_days": min_days_overdue,
            },
            page=page,
            page_size=page_size,
        )
        return self._queries.dispatch(query)


    def fetch_inadimplencia_list(
        self,
        clinic_id: int,
        data_inicio: date,
        data_fim: date,
    ) -> Sequence[OralsinPacienteDTO]:
        """Método auxiliar para obter dados brutos da Oralsin sem persistir."""
        from oralsin_core.adapters.api_clients.oralsin_api_client import OralsinAPIClient
        from oralsin_core.core.application.dtos.oralsin_dtos import InadimplenciaQueryDTO

        client = OralsinAPIClient()
        return client.get_inadimplencia(
            InadimplenciaQueryDTO(
                idClinica=clinic_id,
                dataVencimentoInicio=data_inicio,
                dataVencimentoFim=data_fim,
            )
        )
