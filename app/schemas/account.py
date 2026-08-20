from pydantic import Field

from app.models.enums import AccountType
from app.schemas.common import CamelModel


class CreateAccountInput(CamelModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: AccountType
    broker_name: str | None = Field(None, max_length=100, alias="brokerName")
    currency: str = Field(..., min_length=3, max_length=3)
    starting_balance: float = Field(..., ge=0, alias="startingBalance")
    current_balance: float | None = Field(None, ge=0, alias="currentBalance")


class UpdateAccountInput(CamelModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: AccountType | None = None
    broker_name: str | None = Field(None, max_length=100, alias="brokerName")
    currency: str | None = Field(None, min_length=3, max_length=3)
    current_balance: float | None = Field(None, ge=0, alias="currentBalance")


class UpdateRiskSettingsInput(CamelModel):
    default_risk_percentage: float | None = Field(
        None, gt=0, le=100, alias="defaultRiskPercentage"
    )
    max_risk_per_trade_percentage: float | None = Field(
        None, gt=0, le=100, alias="maxRiskPerTradePercentage"
    )
    max_daily_risk_percentage: float | None = Field(
        None, gt=0, le=100, alias="maxDailyRiskPercentage"
    )
    max_daily_loss_percentage: float | None = Field(
        None, gt=0, le=100, alias="maxDailyLossPercentage"
    )
    max_open_risk_percentage: float | None = Field(
        None, gt=0, le=100, alias="maxOpenRiskPercentage"
    )
    max_trades_per_day: int | None = Field(
        None, gt=0, le=100, alias="maxTradesPerDay"
    )
    max_consecutive_losses: int | None = Field(
        None, gt=0, le=100, alias="maxConsecutiveLosses"
    )
    strict_mode: bool | None = Field(None, alias="strictMode")


class RiskSettingsResponse(CamelModel):
    id: str
    trading_account_id: str = Field(alias="tradingAccountId")
    default_risk_percentage: str = Field(alias="defaultRiskPercentage")
    max_risk_per_trade_percentage: str = Field(alias="maxRiskPerTradePercentage")
    max_daily_risk_percentage: str = Field(alias="maxDailyRiskPercentage")
    max_daily_loss_percentage: str = Field(alias="maxDailyLossPercentage")
    max_open_risk_percentage: str = Field(alias="maxOpenRiskPercentage")
    max_trades_per_day: int = Field(alias="maxTradesPerDay")
    max_consecutive_losses: int = Field(alias="maxConsecutiveLosses")
    strict_mode: bool = Field(alias="strictMode")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class AccountResponse(CamelModel):
    id: str
    name: str
    type: AccountType
    source: str
    broker_name: str | None = Field(alias="brokerName")
    currency: str
    starting_balance: str = Field(alias="startingBalance")
    current_balance: str = Field(alias="currentBalance")
    is_active: bool = Field(alias="isActive")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    risk_settings: RiskSettingsResponse | None = Field(alias="riskSettings")
