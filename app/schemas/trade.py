from datetime import datetime
from math import isfinite
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    ChartTimeframe,
    ExecutionType,
    MarketBias,
    PlanComplianceStatus,
    TradeDirection,
    TradeEmotion,
    TradeStatus,
)


def _normalize_optional_price(value: object) -> float | None:
    if value in ("", None):
        return None

    parsed = float(value) if isinstance(value, (int, float)) else float(str(value))

    if not isfinite(parsed) or parsed <= 0:
        return None

    return parsed


OptionalPriceField = Annotated[
    float | None,
    Field(gt=0),
]


class TradeReviewInput(BaseModel):
    market_bias: Optional[MarketBias] = Field(None, alias="marketBias")
    pre_trade_plan: Optional[str] = Field(None, max_length=5000, alias="preTradePlan")
    post_trade_plan: Optional[str] = Field(None, max_length=5000, alias="postTradePlan")
    pre_trade_emotion: Optional[TradeEmotion] = Field(None, alias="preTradeEmotion")
    post_trade_emotion: Optional[TradeEmotion] = Field(None, alias="postTradeEmotion")
    confidence_score: Optional[int] = Field(None, ge=1, le=10, alias="confidenceScore")
    plan_compliance: Optional[PlanComplianceStatus] = Field(None, alias="planCompliance")
    entry_reason: Optional[str] = Field(None, max_length=2000, alias="entryReason")
    what_went_well: Optional[str] = Field(None, max_length=5000, alias="whatWentWell")
    what_went_wrong: Optional[str] = Field(None, max_length=5000, alias="whatWentWrong")
    notes: Optional[str] = Field(None, max_length=5000)
    lesson: Optional[str] = Field(None, max_length=5000)

    model_config = {"populate_by_name": True}


class CreateTradeInput(BaseModel):
    trading_account_id: str = Field(..., min_length=1, alias="tradingAccountId")
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: TradeDirection
    entry_price: float = Field(..., gt=0, alias="entryPrice")
    volume: float = Field(..., gt=0)
    stop_loss: OptionalPriceField = Field(None, alias="stopLoss")
    take_profit: OptionalPriceField = Field(None, alias="takeProfit")
    executed_at: Optional[datetime] = Field(None, alias="executedAt")
    account_balance_at_entry: Optional[float] = Field(None, ge=0, alias="accountBalanceAtEntry")
    initial_risk_amount: Optional[float] = Field(None, ge=0, alias="initialRiskAmount")
    initial_risk_percentage: Optional[float] = Field(
        None, ge=0, le=100, alias="initialRiskPercentage"
    )
    planned_rr: Optional[float] = Field(None, ge=0, alias="plannedRR")
    strategy_ids: Optional[list[str]] = Field(None, alias="strategyIds")
    tag_ids: Optional[list[str]] = Field(None, alias="tagIds")
    mistake_ids: Optional[list[str]] = Field(None, alias="mistakeIds")
    review: Optional[TradeReviewInput] = None

    model_config = {"populate_by_name": True}

    @field_validator("stop_loss", "take_profit", mode="before")
    @classmethod
    def normalize_optional_prices(cls, value: object) -> float | None:
        if value is None:
            return None
        return _normalize_optional_price(value)


class UpdateTradeInput(BaseModel):
    current_stop_loss: OptionalPriceField = Field(None, alias="currentStopLoss")
    current_take_profit: OptionalPriceField = Field(None, alias="currentTakeProfit")
    chart_timeframe: Optional[ChartTimeframe] = Field(None, alias="chartTimeframe")
    strategy_ids: Optional[list[str]] = Field(None, alias="strategyIds")
    tag_ids: Optional[list[str]] = Field(None, alias="tagIds")
    mistake_ids: Optional[list[str]] = Field(None, alias="mistakeIds")
    review: Optional[TradeReviewInput] = None

    model_config = {"populate_by_name": True}

    @field_validator("current_stop_loss", "current_take_profit", mode="before")
    @classmethod
    def normalize_optional_prices(cls, value: object) -> float | None:
        if value is None:
            return None
        return _normalize_optional_price(value)


class AddExecutionInput(BaseModel):
    type: ExecutionType
    price: float = Field(..., gt=0)
    volume: float = Field(..., gt=0)
    commission: Optional[float] = Field(None, ge=0)
    swap: Optional[float] = Field(None, ge=0)
    fee: Optional[float] = Field(None, ge=0)
    executed_at: Optional[datetime] = Field(None, alias="executedAt")

    model_config = {"populate_by_name": True}


class CloseTradeInput(BaseModel):
    price: float = Field(..., gt=0)
    commission: Optional[float] = Field(None, ge=0)
    swap: Optional[float] = Field(None, ge=0)
    fee: Optional[float] = Field(None, ge=0)
    executed_at: Optional[datetime] = Field(None, alias="executedAt")

    model_config = {"populate_by_name": True}


TradeSort = Literal["openedAt_desc", "openedAt_asc", "netPnl_desc", "netPnl_asc"]


class ListTradesQuery(BaseModel):
    trading_account_id: Optional[str] = Field(None, min_length=1, alias="tradingAccountId")
    symbol: Optional[str] = Field(None, min_length=1)
    status: Optional[TradeStatus] = None
    direction: Optional[TradeDirection] = None
    opened_from: Optional[datetime] = Field(None, alias="openedFrom")
    opened_to: Optional[datetime] = Field(None, alias="openedTo")
    page: Optional[int] = Field(None, gt=0)
    limit: Optional[int] = Field(None, gt=0, le=100)
    sort: Optional[TradeSort] = None

    model_config = {"populate_by_name": True}


UpdateTradeReviewInput = TradeReviewInput
