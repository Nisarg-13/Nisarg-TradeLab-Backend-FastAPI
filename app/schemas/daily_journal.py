from datetime import date, datetime

from pydantic import Field

from app.models.enums import MarketBias
from app.schemas.common import CamelModel


class DailyJournalInput(CamelModel):
    trading_account_id: str = Field(..., min_length=1, alias="tradingAccountId")
    date: datetime
    confidence_score: int | None = Field(None, ge=1, le=10, alias="confidenceScore")
    market_bias: MarketBias | None = Field(None, alias="marketBias")
    pre_trade_plan: str | None = Field(None, max_length=5000, alias="preTradePlan")
    post_trade_plan: str | None = Field(None, max_length=5000, alias="postTradePlan")
    what_went_well: str | None = Field(None, max_length=5000, alias="whatWentWell")
    what_went_wrong: str | None = Field(None, max_length=5000, alias="whatWentWrong")


class UpdateDailyJournalInput(CamelModel):
    confidence_score: int | None = Field(None, ge=1, le=10, alias="confidenceScore")
    market_bias: MarketBias | None = Field(None, alias="marketBias")
    pre_trade_plan: str | None = Field(None, max_length=5000, alias="preTradePlan")
    post_trade_plan: str | None = Field(None, max_length=5000, alias="postTradePlan")
    what_went_well: str | None = Field(None, max_length=5000, alias="whatWentWell")
    what_went_wrong: str | None = Field(None, max_length=5000, alias="whatWentWrong")


class ListDailyJournalQuery(CamelModel):
    trading_account_id: str | None = Field(None, min_length=1, alias="tradingAccountId")
    from_: date | None = Field(None, alias="from")
    to: date | None = None


class DailyJournalResponse(CamelModel):
    id: str
    trading_account_id: str = Field(alias="tradingAccountId")
    date: str
    confidence_score: int | None = Field(alias="confidenceScore")
    market_bias: MarketBias | None = Field(alias="marketBias")
    pre_trade_plan: str | None = Field(alias="preTradePlan")
    post_trade_plan: str | None = Field(alias="postTradePlan")
    what_went_well: str | None = Field(alias="whatWentWell")
    what_went_wrong: str | None = Field(alias="whatWentWrong")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
