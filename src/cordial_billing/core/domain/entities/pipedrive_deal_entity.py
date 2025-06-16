from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class PipedriveDealEntity:
    id: int
    title: str | None
    person_id: int | None
    stage_id: int | None
    pipeline_id: int | None
    value: Decimal | None
    currency: str | None
    status: str | None          # open | won | lost
    add_time: datetime | None
    update_time: datetime | None
    expected_close_date: date | None
    cpf_text: str | None
