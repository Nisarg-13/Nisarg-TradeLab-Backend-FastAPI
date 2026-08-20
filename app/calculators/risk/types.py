from typing import Literal, TypedDict

TradeDirection = Literal["LONG", "SHORT"]
RiskMode = Literal["PERCENTAGE", "FIXED"]
ViolationSeverity = Literal["warning", "critical"]
ExecutionType = Literal["ENTRY", "EXIT"]
TradeStatus = Literal["OPEN", "CLOSED"]


class RiskViolation(TypedDict):
    severity: ViolationSeverity
    code: str
    message: str


class InstrumentSpecInput(TypedDict):
    symbol: str
    contractSize: float
    tickSize: float
    tickValueProfit: float
    tickValueLoss: float
    volumeMin: float
    volumeMax: float
    volumeStep: float


class RiskSettingsInput(TypedDict):
    maxRiskPerTradePercentage: float
    maxDailyRiskPercentage: float
    maxDailyLossPercentage: float
    maxOpenRiskPercentage: float
    maxTradesPerDay: int
    maxConsecutiveLosses: int
    strictMode: bool


class RiskContextInput(TypedDict):
    currentDailyRiskAmount: float
    currentDailyLossAmount: float
    currentOpenRiskAmount: float
    tradesTodayCount: int
    consecutiveLossesCount: int


class CalculateRiskInput(TypedDict, total=False):
    accountBalance: float
    instrument: InstrumentSpecInput
    direction: TradeDirection
    entryPrice: float
    stopLoss: float
    takeProfit: float
    riskMode: RiskMode
    riskPercentage: float
    fixedRiskAmount: float
    riskSettings: RiskSettingsInput
    riskContext: RiskContextInput
    evaluateAccountRules: bool


class CalculateRiskResult(TypedDict):
    accountBalance: float
    riskPercentage: float
    riskAmount: float
    priceDistance: float
    stopDistance: float
    recommendedPositionSize: float
    potentialLoss: float
    potentialProfit: float | None
    riskReward: float | None
    currentDailyRisk: float
    dailyRiskAfterTrade: float
    currentOpenRisk: float
    openRiskAfterTrade: float
    violations: list[RiskViolation]
    blocked: bool
