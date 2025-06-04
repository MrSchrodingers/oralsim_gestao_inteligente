from datetime import date, datetime

from cordial_billing.core.application.dtos.pipeboard_base_model import PDBaseModel


class Deal(PDBaseModel):
    id:                 int
    title:              str     | None = None
    creator_user_id:    int     | None = None
    user_id:            int     | None = None
    owner_id:           int     | None = None
    person_id:          int     | None = None
    org_id:             int     | None = None
    stage_id:           int     | None = None
    pipeline_id:        int     | None = None

    value:              float   | None  = None
    currency:           str     | None  = None

    add_time:           datetime | None = None
    update_time:        datetime | None = None
    stage_change_time:  datetime | None = None # Hora da última mudança de etapa
    close_time:         datetime | None = None # Hora que foi fechado (ganho ou perdido)
    won_time:           datetime | None = None
    lost_time:          datetime | None = None
    expected_close_date:date     | None = None

    status:             str      | None = None # open, won, lost
    probability:        float    | None = None # Probabilidade pode ser float
    lost_reason:        str      | None = None
    visible_to:         int      | None = None # Geralmente é uma string '1', '3', '5', '7'

