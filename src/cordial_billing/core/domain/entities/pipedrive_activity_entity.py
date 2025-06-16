from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class PipedriveActivityEntity:
    id: int
    user_id: int | None
    done: bool | None
    type: str | None
    subject: str | None
    due_date: date | None
    due_time: str | None
    duration: int | None
    add_time: datetime | None
    update_time: datetime | None
    marked_as_done_time: datetime | None
    deal_id: int | None
    person_id: int | None
    org_id: int | None
    project_id: int | None
    note: str | None