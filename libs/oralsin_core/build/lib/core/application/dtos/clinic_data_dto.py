from datetime import datetime

from pydantic import BaseModel


class ClinicDataDTO(BaseModel):
    clinic_id: str
    corporate_name: str | None = None
    acronym: str | None = None
    address_id: str | None = None
    active: bool = False
    franchise: bool = False
    timezone: str | None = None
    harvest_date: datetime | None = None
    first_billing_date: datetime | None = None
    referral_program: bool = False
    show_lp_oralsin: bool = False
    landing_page_url: str | None = None
    oralsin_lp_url: str | None = None
    facebook_url: str | None = None
    facebook_chat_url: str | None = None
    whatsapp_url: str | None = None
    lead_email: str | None = None
