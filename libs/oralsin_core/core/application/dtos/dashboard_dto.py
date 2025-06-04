from dataclasses import dataclass, field


@dataclass(frozen=True)
class PaymentSummaryDTO:
    id: str
    patient: str
    amount: str
    date: str
    status: str

@dataclass(frozen=True)
class StatsDTO:
    totalReceivables: str
    paidThisMonth: str
    pendingPayments: str
    overduePayments: str
    collectionRate: int
    totalContracts: int
    totalPatients: int
    averageDaysOverdue: float
    overdueContracts: int

@dataclass(frozen=True)
class DashboardDTO:
    stats: StatsDTO
    recentPayments: list[PaymentSummaryDTO] = field(default_factory=list)
    pendingPayments: list[PaymentSummaryDTO] = field(default_factory=list)
