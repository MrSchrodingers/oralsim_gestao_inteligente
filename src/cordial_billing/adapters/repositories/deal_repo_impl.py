from re import sub

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cordial_billing.core.application.dtos.pipeboard_deal_dto import Deal
from cordial_billing.core.domain.entities.pipedrive_deal_entity import (
    PipedriveDealEntity,
)
from cordial_billing.core.domain.repositories.deal_repository import DealRepository


def _normalize_cpf(cpf: str) -> str:
    """Remove máscara/pontuação (123.456.789-00 → 12345678900)."""
    return sub(r"\D", "", cpf)


class DealRepoImpl(DealRepository):
    def __init__(self, pipeboard_engine: AsyncEngine):
        self._engine = pipeboard_engine

    async def find_by_cpf(self, cpf: str) -> PipedriveDealEntity | None:
        sql = """
        SELECT d.* FROM negocios d
        JOIN pessoas p ON p.id = d.person_id
        WHERE translate(p.cpf_text, '.-/', '') = :cpf
        ORDER BY d.update_time DESC
        LIMIT 1
        """
        cpf_clean = _normalize_cpf(cpf)

        async with self._engine.connect() as conn:
            result = await conn.execute(text(sql), {"cpf": cpf_clean})
            row = result.mappings().first()

        if not row:
            return None

        dto = Deal.model_validate(row)
        deal_entity = PipedriveDealEntity(
            id=dto.id,
            title=dto.title,
            person_id=dto.person_id,
            stage_id=dto.stage_id,
            pipeline_id=dto.pipeline_id,
            value=dto.value,
            currency=dto.currency,
            status=dto.status,
            add_time=dto.add_time,
            update_time=dto.update_time,
            expected_close_date=dto.expected_close_date,
        )
        return deal_entity
    
    async def find_by_id(self, deal_id: int) -> PipedriveDealEntity | None:
        sql = "SELECT d.*, p.cpf_text FROM negocios d JOIN pessoas p ON p.id = d.person_id WHERE d.id = :id LIMIT 1"
        async with self._engine.connect() as conn:
            row = (await conn.execute(text(sql), {"id": deal_id})).mappings().first()
        if not row:
            return None
        dto = Deal.model_validate(row)
        return PipedriveDealEntity(
            id=dto.id,
            title=dto.title,
            person_id=dto.person_id,
            stage_id=dto.stage_id,
            pipeline_id=dto.pipeline_id,
            value=dto.value,
            currency=dto.currency,
            status=dto.status,
            add_time=dto.add_time,
            update_time=dto.update_time,
            expected_close_date=dto.expected_close_date,
        )

    async def find_cpf_by_deal_id(self, deal_id: int) -> str | None:
        """
        Retorna apenas o CPF (cpf_text) da pessoa associada a um negócio (deal).
        """
        sql = """
        SELECT p.cpf_text
          FROM pessoas p
          JOIN negocios d ON p.id = d.person_id
         WHERE d.id = :id
           LIMIT 1
        """
        async with self._engine.connect() as conn:
            row = (await conn.execute(text(sql), {"id": deal_id})).mappings().first()

        if not row or not row.get("cpf_text"):
            return None

        return _normalize_cpf(row["cpf_text"])