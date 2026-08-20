from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _coerce_positive(value: object, fallback: float) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback

    if parsed <= 0:
        return fallback

    return parsed


def _coerce_non_negative(value: object, fallback: float = 0) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback

    if parsed < 0:
        return fallback

    return parsed


def _optional_mt5_price(value: object) -> float | None:
    if value in ("", None):
        return None

    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

    if parsed <= 0:
        return None

    return parsed


AssetClassLiteral = Literal[
    "FOREX", "COMMODITY", "INDEX", "CRYPTO", "STOCK", "OTHER"
]
DirectionLiteral = Literal["LONG", "SHORT"]
EntryTypeLiteral = Literal["ENTRY", "EXIT"]


class CreateMt5ConnectionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trading_account_id: str = Field(min_length=1, alias="tradingAccountId")


class Mt5ConnectInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mt5_login: str = Field(min_length=1, alias="mt5Login")
    server_name: str = Field(min_length=1, alias="serverName")
    broker_name: str | None = Field(default=None, min_length=1, alias="brokerName")
    currency: str = Field(min_length=3, max_length=3)
    balance: float
    equity: float
    leverage: int | None = Field(default=None, gt=0)
    account_type: str | None = Field(default=None, min_length=1, alias="accountType")
    ea_version: str | None = Field(default=None, min_length=1, alias="eaVersion")

    @field_validator("mt5_login", "server_name", "broker_name", "account_type", "ea_version", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class Mt5HeartbeatInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ea_version: str | None = Field(default=None, min_length=1, alias="eaVersion")

    @field_validator("ea_version", mode="before")
    @classmethod
    def strip_ea_version(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class Mt5AccountSnapshotInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    balance: float
    equity: float
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class Mt5InstrumentInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(min_length=1)
    description: str | None = None
    asset_class: AssetClassLiteral = Field(default="FOREX", alias="assetClass")
    digits: int = Field(ge=0)
    point: Annotated[float, Field(gt=0)] = 0.00001
    tick_size: Annotated[float, Field(gt=0, alias="tickSize")] = 0.00001
    tick_value_profit: float = Field(alias="tickValueProfit")
    tick_value_loss: float = Field(alias="tickValueLoss")
    contract_size: Annotated[float, Field(gt=0, alias="contractSize")] = 1
    volume_min: Annotated[float, Field(ge=0, alias="volumeMin")] = 0.01
    volume_max: Annotated[float, Field(gt=0, alias="volumeMax")] = 100
    volume_step: Annotated[float, Field(gt=0, alias="volumeStep")] = 0.01
    base_currency: str | None = Field(default=None, min_length=3, max_length=3, alias="baseCurrency")
    profit_currency: str | None = Field(default=None, min_length=3, max_length=3, alias="profitCurrency")

    @field_validator("symbol", "description", mode="before")
    @classmethod
    def strip_symbol_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("point", mode="before")
    @classmethod
    def coerce_point(cls, value: object) -> float:
        return _coerce_positive(value, 0.00001)

    @field_validator("tick_size", mode="before")
    @classmethod
    def coerce_tick_size(cls, value: object) -> float:
        return _coerce_positive(value, 0.00001)

    @field_validator("contract_size", mode="before")
    @classmethod
    def coerce_contract_size(cls, value: object) -> float:
        return _coerce_positive(value, 1)

    @field_validator("volume_min", mode="before")
    @classmethod
    def coerce_volume_min(cls, value: object) -> float:
        return _coerce_non_negative(value, 0.01)

    @field_validator("volume_max", mode="before")
    @classmethod
    def coerce_volume_max(cls, value: object) -> float:
        return _coerce_positive(value, 100)

    @field_validator("volume_step", mode="before")
    @classmethod
    def coerce_volume_step(cls, value: object) -> float:
        return _coerce_positive(value, 0.01)


class Mt5InstrumentsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instruments: list[Mt5InstrumentInput] = Field(default_factory=list, max_length=500)

    @field_validator("instruments", mode="before")
    @classmethod
    def sanitize_instruments(cls, value: object) -> object:
        if not isinstance(value, list):
            return value

        sanitized: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip()
            if not symbol:
                continue
            sanitized.append({**item, "symbol": symbol})

        return sanitized


class Mt5DealInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deal_id: str = Field(min_length=1, alias="dealId")
    position_id: str = Field(min_length=1, alias="positionId")
    symbol: str = Field(min_length=1)
    direction: DirectionLiteral
    entry_type: EntryTypeLiteral = Field(alias="entryType")
    volume: Annotated[float, Field(gt=0)] = 0.00000001
    price: Annotated[float, Field(gt=0)] = 0.00000001
    profit: float = 0
    commission: float = 0
    swap: float = 0
    fee: float = 0
    executed_at: datetime = Field(alias="executedAt")
    asset_class: AssetClassLiteral = Field(default="FOREX", alias="assetClass")
    stop_loss: float | None = Field(default=None, gt=0, alias="stopLoss")
    take_profit: float | None = Field(default=None, gt=0, alias="takeProfit")

    @field_validator("deal_id", "position_id", "symbol", mode="before")
    @classmethod
    def strip_deal_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("volume", mode="before")
    @classmethod
    def coerce_volume(cls, value: object) -> float:
        return _coerce_positive(value, 0.00000001)

    @field_validator("price", mode="before")
    @classmethod
    def coerce_price(cls, value: object) -> float:
        return _coerce_positive(value, 0.00000001)

    @field_validator("stop_loss", "take_profit", mode="before")
    @classmethod
    def coerce_optional_price(cls, value: object) -> float | None:
        return _optional_mt5_price(value)


class Mt5DealsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deals: list[Mt5DealInput] = Field(min_length=1, max_length=500)


class Mt5PositionLevelInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    position_id: str = Field(min_length=1, alias="positionId")
    symbol: str | None = Field(default=None, min_length=1)
    opened_at: datetime | None = Field(default=None, alias="openedAt")
    stop_loss: float | None = Field(default=None, gt=0, alias="stopLoss")
    take_profit: float | None = Field(default=None, gt=0, alias="takeProfit")

    @field_validator("position_id", "symbol", mode="before")
    @classmethod
    def strip_level_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("stop_loss", "take_profit", mode="before")
    @classmethod
    def coerce_optional_price(cls, value: object) -> float | None:
        return _optional_mt5_price(value)


class Mt5PositionLevelsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    levels: list[Mt5PositionLevelInput] = Field(default_factory=list, max_length=500)


class Mt5PositionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    position_id: str = Field(min_length=1, alias="positionId")
    symbol: str = Field(min_length=1)
    direction: DirectionLiteral
    volume: Annotated[float, Field(gt=0)]
    open_price: Annotated[float, Field(gt=0, alias="openPrice")]
    current_price: Annotated[float, Field(gt=0, alias="currentPrice")]
    stop_loss: float | None = Field(default=None, gt=0, alias="stopLoss")
    take_profit: float | None = Field(default=None, gt=0, alias="takeProfit")
    floating_pnl: float = Field(alias="floatingPnl")
    swap: float = 0
    opened_at: datetime = Field(alias="openedAt")
    snapshot_at: datetime = Field(alias="snapshotAt")
    asset_class: AssetClassLiteral = Field(default="FOREX", alias="assetClass")

    @field_validator("position_id", "symbol", mode="before")
    @classmethod
    def strip_position_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("volume", mode="before")
    @classmethod
    def coerce_volume(cls, value: object) -> float:
        return _coerce_positive(value, 0.00000001)

    @field_validator("open_price", "current_price", mode="before")
    @classmethod
    def coerce_prices(cls, value: object) -> float:
        return _coerce_positive(value, 0.00000001)

    @field_validator("stop_loss", "take_profit", mode="before")
    @classmethod
    def coerce_optional_price(cls, value: object) -> float | None:
        return _optional_mt5_price(value)


class Mt5PositionsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    positions: list[Mt5PositionInput] = Field(default_factory=list, max_length=500)


Mt5TradeEventType = Literal[
    "TRADE_OPEN",
    "TRADE_CLOSE",
    "PARTIAL_CLOSE",
    "SL_CHANGED",
    "TP_CHANGED",
    "VOLUME_CHANGED",
]


class Mt5TradeEventInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(min_length=1, alias="eventId")
    event_type: Mt5TradeEventType = Field(alias="eventType")
    position_id: str = Field(min_length=1, alias="positionId")
    symbol: str | None = Field(default=None, min_length=1)
    direction: DirectionLiteral | None = None
    stop_loss: float | None = Field(default=None, ge=0, alias="stopLoss")
    take_profit: float | None = Field(default=None, ge=0, alias="takeProfit")
    volume: float | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, gt=0)
    occurred_at: datetime = Field(alias="occurredAt")
    deal: Mt5DealInput | None = None

    @field_validator("event_id", "position_id", "symbol", mode="before")
    @classmethod
    def strip_event_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class Mt5TradeEventsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    events: list[Mt5TradeEventInput] = Field(min_length=1, max_length=200)


class Mt5ReconcileInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    since: datetime | None = None
    positions: list[Mt5PositionInput] = Field(default_factory=list, max_length=500)
    deals: list[Mt5DealInput] = Field(default_factory=list, max_length=500)
    instruments: list[Mt5InstrumentInput] | None = Field(default=None, max_length=500)


class RecalculateImportedTradesInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trading_account_id: str | None = Field(default=None, alias="tradingAccountId")

    @model_validator(mode="after")
    def require_trading_account_id(self) -> "RecalculateImportedTradesInput":
        if not self.trading_account_id:
            raise ValueError("tradingAccountId is required.")
        return self
