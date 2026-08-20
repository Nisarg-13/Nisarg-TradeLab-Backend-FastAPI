from typing import Literal

from pydantic import Field, model_validator

from app.models.enums import TradeDirection
from app.schemas.common import CamelModel

RiskMode = Literal["PERCENTAGE", "FIXED"]


class CalculateRiskBody(CamelModel):
    account_balance: float = Field(..., gt=0, alias="accountBalance")
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: TradeDirection
    entry_price: float = Field(..., gt=0, alias="entryPrice")
    stop_loss: float = Field(..., gt=0, alias="stopLoss")
    take_profit: float | None = Field(None, gt=0, alias="takeProfit")
    risk_mode: RiskMode = Field(alias="riskMode")
    risk_percentage: float | None = Field(None, gt=0, le=100, alias="riskPercentage")
    fixed_risk_amount: float | None = Field(None, gt=0, alias="fixedRiskAmount")

    @model_validator(mode="after")
    def validate_risk_mode_fields(self) -> "CalculateRiskBody":
        if self.risk_mode == "PERCENTAGE" and self.risk_percentage is None:
            raise ValueError("riskPercentage is required when riskMode is PERCENTAGE")
        if self.risk_mode == "FIXED" and self.fixed_risk_amount is None:
            raise ValueError("fixedRiskAmount is required when riskMode is FIXED")
        return self


class RiskViolationResponse(CamelModel):
    severity: str
    code: str
    message: str


class CalculateRiskResponse(CamelModel):
    symbol: str
    direction: TradeDirection
    entry_price: str = Field(alias="entryPrice")
    stop_loss: str = Field(alias="stopLoss")
    take_profit: str | None = Field(alias="takeProfit")
    risk_mode: RiskMode = Field(alias="riskMode")
    account_balance: str = Field(alias="accountBalance")
    risk_percentage: str = Field(alias="riskPercentage")
    risk_amount: str = Field(alias="riskAmount")
    price_distance: str = Field(alias="priceDistance")
    stop_distance: str = Field(alias="stopDistance")
    recommended_position_size: str = Field(alias="recommendedPositionSize")
    potential_loss: str = Field(alias="potentialLoss")
    potential_profit: str | None = Field(alias="potentialProfit")
    risk_reward: str | None = Field(alias="riskReward")
    current_daily_risk: str = Field(alias="currentDailyRisk")
    daily_risk_after_trade: str = Field(alias="dailyRiskAfterTrade")
    current_open_risk: str = Field(alias="currentOpenRisk")
    open_risk_after_trade: str = Field(alias="openRiskAfterTrade")
    violations: list[RiskViolationResponse]
    blocked: bool
