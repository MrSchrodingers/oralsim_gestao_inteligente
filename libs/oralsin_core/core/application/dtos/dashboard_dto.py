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
class AmicableSummaryDTO:
    totalCases: int
    withPipeboard: int
    withoutPipeboard: int
    overdueMinDaysPlus: int          # idem sua lógica atual (limiar do regime)
    overdueInAmicable: int           # parcelas atrasadas em contratos CA
    receivablesWithDebt: int         # quantas parcelas a receber estão com CollectionCase (aberto)
    recoveredCA: int                 # parcelas pagas em contratos CA
    recoveredCAAmount: float         # soma paga em contratos CA

@dataclass(frozen=True)
class ReceivablesSummaryDTO:
    receivablesTotalCount: int       # total de parcelas a receber (pendentes + vencidas)
    overduePatients: int
    preOverduePatients: int
    noBilling: int
    recoveredGR: int                 # parcelas pagas em contratos GR
    recoveredGRAmount: float         # soma paga em contratos GR

@dataclass(frozen=True)
class CollectionSummaryDTO:
    totalCases: int
    withPipeboard: int
    withoutPipeboard: int
    overdueMinDaysPlus: int
    overduePatients: int
    preOverduePatients: int
    noBilling: int

    recoveredCA: int                              # qtd de parcelas recuperadas via Cobrança Amigável
    recoveredGR: int                              # qtd de parcelas recuperadas via Gestão de Recebíveis
    receivablesTotalCount: int                    # total de parcelas a receber (pendentes + vencidas)
    receivablesWithDebt: int                      # quantas dessas estão “em Debt” (caso de cobrança aberto)
    overdueInAmicable: int                        # quantas vencidas estão em cobrança amigável
    recoveredCAAmount: float                      # soma recuperada via CA
    recoveredGRAmount: float                      # soma recuperada via GR
    roi: float | None = None                      # ROI (%). None se custo não configurado
    
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
    amicable: AmicableSummaryDTO | None = None       
    receivables: ReceivablesSummaryDTO | None = None 
    monthlyReceivables: list[MonthlyReceivableDTO] | None = None
    lastNotifications: list[NotificationActivityDTO] | None = None
    roi: float | None = None                      # ROI global opcional
