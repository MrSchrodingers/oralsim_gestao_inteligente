from dataclasses import dataclass, field


@dataclass(frozen=True)
class PaymentSummaryDTO:
    id: str
    patient: str
    amount: str
    date: str
    status: str

@dataclass(frozen=True)
class NotificationSummaryDTO:
    pendingSchedules: int
    sentNotifications: int
    pendingCalls: int
    byStep: dict[int, int]


@dataclass(frozen=True)
class CollectionSummaryDTO:
    totalCases: int
    withPipeboard: int
    withoutPipeboard: int
    overdueMinDaysPlus: int
    overduePatients: int
    preOverduePatients: int
    noBilling: int
    
@dataclass(frozen=True)
class MonthlyReceivableDTO:
    month: str       
    paid: float       
    receivable: float

@dataclass(frozen=True)
class NotificationActivityDTO:
    id: str
    channel: str     
    patient: str
    sent_at: str      
    success: bool
    
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
    notification: NotificationSummaryDTO | None = None
    collection: CollectionSummaryDTO | None = None
    monthlyReceivables: list[MonthlyReceivableDTO] | None = None
    lastNotifications: list[NotificationActivityDTO] | None = None
