from pydantic import Field

from app.models.enums import AssetClass
from app.schemas.common import CamelModel


class CreateInstrumentInput(CamelModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    description: str | None = Field(None, max_length=100)
    asset_class: AssetClass = Field(alias="assetClass")
    digits: int = Field(..., ge=0, le=10)
    point: float = Field(..., gt=0)
    tick_size: float = Field(..., gt=0, alias="tickSize")
    tick_value_profit: float = Field(..., gt=0, alias="tickValueProfit")
    tick_value_loss: float = Field(..., gt=0, alias="tickValueLoss")
    contract_size: float = Field(..., gt=0, alias="contractSize")
    volume_min: float = Field(..., gt=0, alias="volumeMin")
    volume_max: float = Field(..., gt=0, alias="volumeMax")
    volume_step: float = Field(..., gt=0, alias="volumeStep")
    base_currency: str | None = Field(None, min_length=3, max_length=3, alias="baseCurrency")
    profit_currency: str | None = Field(
        None, min_length=3, max_length=3, alias="profitCurrency"
    )


class UpdateInstrumentInput(CamelModel):
    symbol: str | None = Field(None, min_length=1, max_length=20)
    description: str | None = Field(None, max_length=100)
    asset_class: AssetClass | None = Field(None, alias="assetClass")
    digits: int | None = Field(None, ge=0, le=10)
    point: float | None = Field(None, gt=0)
    tick_size: float | None = Field(None, gt=0, alias="tickSize")
    tick_value_profit: float | None = Field(None, gt=0, alias="tickValueProfit")
    tick_value_loss: float | None = Field(None, gt=0, alias="tickValueLoss")
    contract_size: float | None = Field(None, gt=0, alias="contractSize")
    volume_min: float | None = Field(None, gt=0, alias="volumeMin")
    volume_max: float | None = Field(None, gt=0, alias="volumeMax")
    volume_step: float | None = Field(None, gt=0, alias="volumeStep")
    base_currency: str | None = Field(None, min_length=3, max_length=3, alias="baseCurrency")
    profit_currency: str | None = Field(
        None, min_length=3, max_length=3, alias="profitCurrency"
    )


class InstrumentResponse(CamelModel):
    id: str
    trading_account_id: str = Field(alias="tradingAccountId")
    symbol: str
    description: str | None
    asset_class: AssetClass = Field(alias="assetClass")
    digits: int
    point: str
    tick_size: str = Field(alias="tickSize")
    tick_value_profit: str = Field(alias="tickValueProfit")
    tick_value_loss: str = Field(alias="tickValueLoss")
    contract_size: str = Field(alias="contractSize")
    volume_min: str = Field(alias="volumeMin")
    volume_max: str = Field(alias="volumeMax")
    volume_step: str = Field(alias="volumeStep")
    base_currency: str | None = Field(alias="baseCurrency")
    profit_currency: str | None = Field(alias="profitCurrency")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
