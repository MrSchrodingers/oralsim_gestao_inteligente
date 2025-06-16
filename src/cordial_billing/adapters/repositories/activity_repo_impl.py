from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cordial_billing.core.application.dtos.pipeboard_activity_dto import Activity
from cordial_billing.core.domain.entities.pipedrive_activity_entity import PipedriveActivityEntity
from cordial_billing.core.domain.repositories.activity_repository import ActivityRepository

_SQL_ACORDO = """
SELECT *
  FROM atividades
 WHERE type = 'call' AND id > :after
 ORDER BY id ASC
 LIMIT :limit
"""

class ActivityRepoImpl(ActivityRepository):
    """Somente acesso ao banco; sem side-effects."""

    def __init__(self, pipeboard_engine: AsyncEngine):
        self._engine = pipeboard_engine

    async def list_acordo_fechado(self, after_id: int, limit: int = 100) -> list[PipedriveActivityEntity]:
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(text(_SQL_ACORDO), {"after": after_id, "limit": limit})
            ).mappings().all()

        return [
            PipedriveActivityEntity(
                id=dto.id,
                user_id=dto.user_id,
                done=dto.done,
                type=dto.type,
                subject=dto.subject,
                due_date=dto.due_date,
                due_time=dto.due_time,
                duration=dto.duration,
                add_time=dto.add_time,
                update_time=dto.update_time,
                marked_as_done_time=dto.marked_as_done_time,
                deal_id=dto.deal_id,
                person_id=dto.person_id,
                org_id=dto.org_id,
                project_id=dto.project_id,
                note=dto.note,
            )
            for dto in map(Activity.model_validate, rows)
        ]
