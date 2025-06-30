from re import sub

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cordial_billing.core.domain.repositories.organization_repository import (
    OrganizationRepository,
)


def _normalize_cnpj(cnpj: str) -> str:
    return sub(r'\D', '', cnpj)


class OrganizationRepoImpl(OrganizationRepository):
    """
    Retorna o `id` da organização (== id no Pipedrive) a partir do CNPJ
    armazenado em Pipeboard. NÃO cria se não encontrar.
    """

    def __init__(self, pipeboard_engine: AsyncEngine) -> None:
        self._engine = pipeboard_engine

    async def find_id_by_cnpj(self, cnpj: str) -> int | None:
        sql = """
            SELECT id
              FROM organizacoes
             WHERE translate(cnpj_text, './-', '') = :cnpj
             LIMIT 1
        """
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(text(sql), {"cnpj": _normalize_cnpj(cnpj)})
            ).mappings().first()
        return row["id"] if row else None
