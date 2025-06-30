from dataclasses import dataclass


@dataclass(frozen=True)
class ClinicSummaryDTO:
    id: str
    name: str
    total_patients: int
    active_patients: int
    receivables: int
    collection_cases: int
    monthly_revenue: str