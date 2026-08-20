from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class Emotion(str, Enum):
    CALM = "CALM"
    CONFIDENT = "CONFIDENT"
    FEAR = "FEAR"
    FOMO = "FOMO"
    GREED = "GREED"
    IMPATIENT = "IMPATIENT"
    REVENGE = "REVENGE"
    OTHER = "OTHER"


class PlanComplianceFilter(str, Enum):
    FOLLOWED = "FOLLOWED"
    PARTIALLY_FOLLOWED = "PARTIALLY_FOLLOWED"
    DID_NOT_FOLLOW = "DID_NOT_FOLLOW"
    NOT_REVIEWED = "NOT_REVIEWED"


class MarketBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class TradingSession(str, Enum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    OVERLAP = "OVERLAP"
    NEW_YORK = "NEW_YORK"
    OFF_HOURS = "OFF_HOURS"


class TradeResult(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


class HeatmapMetric(str, Enum):
    PNL = "pnl"
    AVERAGE_R = "averageR"
    EXPECTANCY = "expectancy"
    WIN_RATE = "winRate"
    TRADE_COUNT = "tradeCount"


class PeriodComparisonMode(str, Enum):
    LATEST_20_VS_PREVIOUS_20 = "LATEST_20_VS_PREVIOUS_20"
    FIRST_50_VS_LATEST_50 = "FIRST_50_VS_LATEST_50"
    THIS_MONTH_VS_LAST_MONTH = "THIS_MONTH_VS_LAST_MONTH"
    CUSTOM = "CUSTOM"


class AnalyticsQuery(BaseModel):
    trading_account_id: Optional[str] = Field(None, min_length=1, alias="tradingAccountId")
    closed_from: Optional[datetime] = Field(None, alias="closedFrom")
    closed_to: Optional[datetime] = Field(None, alias="closedTo")
    symbol: Optional[str] = Field(None, min_length=1)
    strategy_id: Optional[str] = Field(None, min_length=1, alias="strategyId")
    tag_id: Optional[str] = Field(None, min_length=1, alias="tagId")
    direction: Optional[Direction] = None
    mistake_id: Optional[str] = Field(None, min_length=1, alias="mistakeId")
    pre_trade_emotion: Optional[Emotion] = Field(None, alias="preTradeEmotion")
    post_trade_emotion: Optional[Emotion] = Field(None, alias="postTradeEmotion")
    followed_plan: Optional[bool] = Field(None, alias="followedPlan")
    plan_compliance: Optional[PlanComplianceFilter] = Field(None, alias="planCompliance")
    market_bias: Optional[MarketBias] = Field(None, alias="marketBias")
    confidence_min: Optional[int] = Field(None, ge=1, le=10, alias="confidenceMin")
    confidence_max: Optional[int] = Field(None, ge=1, le=10, alias="confidenceMax")
    risk_min: Optional[float] = Field(None, ge=0, alias="riskMin")
    risk_max: Optional[float] = Field(None, ge=0, alias="riskMax")
    session: Optional[TradingSession] = None
    result: Optional[TradeResult] = None

    model_config = {"populate_by_name": True}

    @field_validator("followed_plan", mode="before")
    @classmethod
    def parse_followed_plan(cls, value: object) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if value == "true":
            return True
        if value == "false":
            return False
        return value  # type: ignore[return-value]


class HeatmapQuery(AnalyticsQuery):
    metric: HeatmapMetric = HeatmapMetric.PNL


class PeriodComparisonQuery(AnalyticsQuery):
    mode: PeriodComparisonMode
    period_a_from: Optional[datetime] = Field(None, alias="periodAFrom")
    period_a_to: Optional[datetime] = Field(None, alias="periodATo")
    period_b_from: Optional[datetime] = Field(None, alias="periodBFrom")
    period_b_to: Optional[datetime] = Field(None, alias="periodBTo")

    model_config = {"populate_by_name": True}
