from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from oralsin_core.core.domain.entities._base import EntityMixin
from oralsin_core.core.domain.entities.address_entity import AddressEntity

if TYPE_CHECKING:
    from plugins.django_interface.models import ClinicData as ClinicDataModel


@dataclass(slots=True)
class ClinicDataEntity(EntityMixin):
    # ─── keys ───────────────────────────────────────────────────────────
    id: uuid.UUID
    clinic_id: uuid.UUID
    oralsin_clinic_id: int | None

    # ─── corporate info ─────────────────────────────────────────────────
    corporate_name: str | None = None
    acronym: str | None = None

    # ─── address (FK) ───────────────────────────────────────────────────
    address: AddressEntity | None = None

    # ─── flags / metadata ───────────────────────────────────────────────
    active: bool = True
    franchise: bool = False
    timezone: str | None = None
    harvest_date: date | None = None
    first_billing_date: date | None = None
    referral_program: bool = False
    show_lp_oralsin: bool = False

    # ─── urls / contacts ───────────────────────────────────────────────
    landing_page_url: str | None = None
    oralsin_lp_url: str | None = None
    facebook_url: str | None = None
    facebook_chat_url: str | None = None
    whatsapp_url: str | None = None
    lead_email: str | None = None

    # ─── timestamps ────────────────────────────────────────────────────
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # ──────────────────────────────────────────────────────────────────
    # helpers
    # ──────────────────────────────────────────────────────────────────
    def full_display(self) -> str:
        parts = [self.corporate_name or "", f"({self.acronym})" if self.acronym else ""]
        return " ".join(p for p in parts if p).strip()

    # ──────────────────────────────────────────────────────────────────
    # factory – convert model → entity (handles missing FKs safely)
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def from_model(cls, m: ClinicDataModel) -> ClinicDataEntity:
        # Safely load related address, avoiding DoesNotExist errors
        addr_ent: AddressEntity | None = None
        if getattr(m, "address_id", None):
            try:
                addr_model = m.address
            except m._meta.get_field("address").related_model.DoesNotExist:
                addr_model = None
            if addr_model:
                addr_ent = AddressEntity.from_model(addr_model)

        return cls(
            id=m.id,
            clinic_id=m.clinic_id,
            oralsin_clinic_id=getattr(m.clinic, "oralsin_clinic_id", None),
            corporate_name=getattr(m, "corporate_name", None),
            acronym=getattr(m, "acronym", None),
            address=addr_ent,
            active=getattr(m, "active", True),
            franchise=getattr(m, "franchise", False),
            timezone=getattr(m, "timezone", None),
            harvest_date=getattr(m, "harvest_date", None),
            first_billing_date=getattr(m, "first_billing_date", None),
            referral_program=getattr(m, "referral_program", False),
            show_lp_oralsin=getattr(m, "show_lp_oralsin", False),
            landing_page_url=getattr(m, "landing_page_url", None),
            oralsin_lp_url=getattr(m, "oralsin_lp_url", None),
            facebook_url=getattr(m, "facebook_url", None),
            facebook_chat_url=getattr(m, "facebook_chat_url", None),
            whatsapp_url=getattr(m, "whatsapp_url", None),
            lead_email=getattr(m, "lead_email", None),
            created_at=getattr(m, "created_at", None),
            updated_at=getattr(m, "updated_at", None),
        )
