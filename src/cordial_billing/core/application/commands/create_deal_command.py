from dataclasses import dataclass

from notification_billing.core.domain.entities._base import EntityMixin


@dataclass(slots=True)
class CreatePipedriveDealCommand(EntityMixin):
    """Command to create a deal in Pipedrive for a collection case."""

    collection_case_id: str