from datetime import date, datetime

from cordial_billing.core.application.dtos.pipeboard_base_model import PDBaseModel


class Activity(PDBaseModel):
    id: int
    user_id: int | None = None
    done: bool | None = None
    type: str | None = None
    subject: str | None = None
    due_date: date | None = None
    due_time: str | None = None
    duration: int | None = None
    add_time: datetime | None = None
    update_time: datetime | None = None
    marked_as_done_time: datetime | None = None
    deal_id: int | None = None
    person_id: int | None = None
    org_id: int | None = None
    project_id: int | None = None
    note: str | None = None