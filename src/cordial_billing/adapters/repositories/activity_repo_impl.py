from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cordial_billing.core.application.dtos.pipeboard_activity_dto import Activity
from cordial_billing.core.domain.entities.pipedrive_activity_entity import PipedriveActivityEntity
from cordial_billing.core.domain.repositories.activity_repository import ActivityRepository

_SQL_ACORDO = """
SELECT *
  FROM atividades
 WHERE type = 'acordo_fechado'
   AND id > CAST(:after AS BIGINT)
 ORDER BY id ASC
 LIMIT :limit
"""

_SQL_UPSERT = """
INSERT INTO atividades (
    id, user_id, done, type, subject,
    due_date, due_time, duration,
    add_time, update_time, marked_as_done_time,
    deal_id, person_id, org_id, project_id, note
) VALUES (
    :id, :user_id, :done, :type, :subject,
    :due_date, :due_time, :duration,
    :add_time, :update_time, :marked_as_done_time,
    :deal_id, :person_id, :org_id, :project_id, :note
)
ON CONFLICT (id) DO UPDATE SET
    user_id             = EXCLUDED.user_id,
    done                = EXCLUDED.done,
    type                = EXCLUDED.type,
    subject             = EXCLUDED.subject,
    due_date            = EXCLUDED.due_date,
    due_time            = EXCLUDED.due_time,
    duration            = EXCLUDED.duration,
    add_time            = EXCLUDED.add_time,
    update_time         = EXCLUDED.update_time,
    marked_as_done_time = EXCLUDED.marked_as_done_time,
    deal_id             = EXCLUDED.deal_id,
    person_id           = EXCLUDED.person_id,
    org_id              = EXCLUDED.org_id,
    project_id          = EXCLUDED.project_id,
    note                = EXCLUDED.note
"""

class ActivityRepoImpl(ActivityRepository):
    """Somente acesso ao banco; sem side-effects."""

    def __init__(self, pipeboard_engine: AsyncEngine):
        self._engine = pipeboard_engine

    @staticmethod
    def _to_date(val):
        if isinstance(val, date):      # já é date
            return val
        if isinstance(val, str) and val:
            # aceita 'YYYY-MM-DD' ou 'YYYY-MM-DDTHH:MM:SSZ'
            try:
                return date.fromisoformat(val[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_datetime(val):
        if isinstance(val, datetime):  # já é datetime
            return val
        if isinstance(val, str) and val:
            try:
                return datetime.fromisoformat(val.replace('Z', '+00:00'))
            except ValueError:
                return None
        return None

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
        
    async def save_from_pipedrive_json(self, data: dict[str, Any]) -> None:
        """
        Upsert direto na tabela *atividades* a partir do JSON devolvido
        pelo endpoint `/activities` do Pipedrive.
        """
        async with self._engine.begin() as conn:
            await conn.execute(
                text(_SQL_UPSERT),
                {
                    "id":                  data["id"],
                    "user_id":             data.get("user_id"),
                    "done":                data.get("done"),
                    "type":                data.get("type"),
                    "subject":             data.get("subject"),
                    "due_date":            self._to_date(data.get("due_date")),
                    "due_time":            data.get("due_time"),
                    "duration":            data.get("duration"),
                    "add_time":            self._to_datetime(data.get("add_time")),
                    "update_time":         self._to_datetime(data.get("update_time")),
                    "marked_as_done_time": self._to_datetime(data.get("marked_as_done_time")),
                    "deal_id":             data.get("deal_id"),
                    "person_id":           data.get("person_id"),
                    "org_id":              data.get("org_id"),
                    "project_id":          data.get("project_id"),
                    "note":                data.get("note"),
                },
            )
