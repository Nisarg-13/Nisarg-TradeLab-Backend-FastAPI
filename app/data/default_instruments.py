from dataclasses import dataclass
from typing import TypedDict

from app.models.enums import AssetClass


class DefaultInstrumentSpec(TypedDict, total=False):
    symbol: str
    description: str
    asset_class: AssetClass
    digits: int
    point: float
    tick_size: float
    tick_value_profit: float
    tick_value_loss: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    base_currency: str
    profit_currency: str


@dataclass(frozen=True, slots=True)
class ForexTemplate:
    digits: int
    point: float
    tick_size: float
    tick_value_profit: float
    tick_value_loss: float


STANDARD_FOREX = ForexTemplate(
    digits=5,
    point=0.00001,
    tick_size=0.00001,
    tick_value_profit=1,
    tick_value_loss=1,
)

JPY_FOREX = ForexTemplate(
    digits=3,
    point=0.001,
    tick_size=0.001,
    tick_value_profit=0.67,
    tick_value_loss=0.67,
)


def _format_pair_name(symbol: str) -> str:
    return f"{symbol[:3]}/{symbol[3:6]}"


def _create_forex_pair(
    symbol: str,
    description: str,
    base_currency: str,
    profit_currency: str,
    template: ForexTemplate = STANDARD_FOREX,
) -> DefaultInstrumentSpec:
    return {
        "symbol": symbol,
        "description": description,
        "asset_class": AssetClass.FOREX,
        "digits": template.digits,
        "point": template.point,
        "tick_size": template.tick_size,
        "tick_value_profit": template.tick_value_profit,
        "tick_value_loss": template.tick_value_loss,
        "contract_size": 100000,
        "volume_min": 0.01,
        "volume_max": 100,
        "volume_step": 0.01,
        "base_currency": base_currency,
        "profit_currency": profit_currency,
    }


def _forex_major(
    symbol: str,
    base_currency: str,
    profit_currency: str,
    label: str,
) -> DefaultInstrumentSpec:
    template = JPY_FOREX if profit_currency == "JPY" or base_currency == "JPY" else STANDARD_FOREX
    return _create_forex_pair(
        symbol,
        f"{label} ({_format_pair_name(symbol)})",
        base_currency,
        profit_currency,
        template,
    )


def _forex_cross(
    symbol: str,
    base_currency: str,
    profit_currency: str,
) -> DefaultInstrumentSpec:
    template = JPY_FOREX if base_currency == "JPY" or profit_currency == "JPY" else STANDARD_FOREX
    return _create_forex_pair(
        symbol,
        f"{_format_pair_name(symbol)} cross",
        base_currency,
        profit_currency,
        template,
    )


FOREX_MAJORS: list[DefaultInstrumentSpec] = [
    _forex_major("EURUSD", "EUR", "USD", "Euro vs US Dollar"),
    _forex_major("GBPUSD", "GBP", "USD", "British Pound vs US Dollar"),
    _forex_major("USDJPY", "USD", "JPY", "US Dollar vs Japanese Yen"),
    _forex_major("USDCHF", "USD", "CHF", "US Dollar vs Swiss Franc"),
    _forex_major("USDCAD", "USD", "CAD", "US Dollar vs Canadian Dollar"),
    _forex_major("AUDUSD", "AUD", "USD", "Australian Dollar vs US Dollar"),
    _forex_major("NZDUSD", "NZD", "USD", "New Zealand Dollar vs US Dollar"),
]

FOREX_CROSSES: list[DefaultInstrumentSpec] = [
    _forex_cross("EURGBP", "EUR", "GBP"),
    _forex_cross("EURJPY", "EUR", "JPY"),
    _forex_cross("EURCHF", "EUR", "CHF"),
    _forex_cross("EURAUD", "EUR", "AUD"),
    _forex_cross("EURCAD", "EUR", "CAD"),
    _forex_cross("EURNZD", "EUR", "NZD"),
    _forex_cross("GBPJPY", "GBP", "JPY"),
    _forex_cross("GBPCHF", "GBP", "CHF"),
    _forex_cross("GBPAUD", "GBP", "AUD"),
    _forex_cross("GBPCAD", "GBP", "CAD"),
    _forex_cross("GBPNZD", "GBP", "NZD"),
    _forex_cross("AUDJPY", "AUD", "JPY"),
    _forex_cross("AUDCAD", "AUD", "CAD"),
    _forex_cross("AUDNZD", "AUD", "NZD"),
    _forex_cross("AUDCHF", "AUD", "CHF"),
    _forex_cross("NZDJPY", "NZD", "JPY"),
    _forex_cross("NZDCAD", "NZD", "CAD"),
    _forex_cross("NZDCHF", "NZD", "CHF"),
    _forex_cross("CADJPY", "CAD", "JPY"),
    _forex_cross("CADCHF", "CAD", "CHF"),
    _forex_cross("CHFJPY", "CHF", "JPY"),
]

FOREX_USD_EXOTICS: list[DefaultInstrumentSpec] = [
    _forex_major("USDSEK", "USD", "SEK", "US Dollar vs Swedish Krona"),
    _forex_major("USDNOK", "USD", "NOK", "US Dollar vs Norwegian Krone"),
    _forex_major("USDDKK", "USD", "DKK", "US Dollar vs Danish Krone"),
    _forex_major("USDPLN", "USD", "PLN", "US Dollar vs Polish Zloty"),
    _forex_major("USDTRY", "USD", "TRY", "US Dollar vs Turkish Lira"),
    _forex_major("USDZAR", "USD", "ZAR", "US Dollar vs South African Rand"),
    _forex_major("USDMXN", "USD", "MXN", "US Dollar vs Mexican Peso"),
    _forex_major("USDSGD", "USD", "SGD", "US Dollar vs Singapore Dollar"),
    _forex_major("USDHKD", "USD", "HKD", "US Dollar vs Hong Kong Dollar"),
    _forex_major("USDCNH", "USD", "CNH", "US Dollar vs Chinese Yuan"),
]

COMMODITIES: list[DefaultInstrumentSpec] = [
    {
        "symbol": "XAUUSD",
        "description": "Gold vs US Dollar",
        "asset_class": AssetClass.COMMODITY,
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value_profit": 1,
        "tick_value_loss": 1,
        "contract_size": 100,
        "volume_min": 0.01,
        "volume_max": 50,
        "volume_step": 0.01,
        "base_currency": "XAU",
        "profit_currency": "USD",
    },
    {
        "symbol": "XAGUSD",
        "description": "Silver vs US Dollar",
        "asset_class": AssetClass.COMMODITY,
        "digits": 3,
        "point": 0.001,
        "tick_size": 0.001,
        "tick_value_profit": 5,
        "tick_value_loss": 5,
        "contract_size": 5000,
        "volume_min": 0.01,
        "volume_max": 50,
        "volume_step": 0.01,
        "base_currency": "XAG",
        "profit_currency": "USD",
    },
    {
        "symbol": "USOIL",
        "description": "US Crude Oil (WTI)",
        "asset_class": AssetClass.COMMODITY,
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value_profit": 1,
        "tick_value_loss": 1,
        "contract_size": 1000,
        "volume_min": 0.01,
        "volume_max": 100,
        "volume_step": 0.01,
        "profit_currency": "USD",
    },
    {
        "symbol": "UKOIL",
        "description": "UK Brent Crude Oil",
        "asset_class": AssetClass.COMMODITY,
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value_profit": 1,
        "tick_value_loss": 1,
        "contract_size": 1000,
        "volume_min": 0.01,
        "volume_max": 100,
        "volume_step": 0.01,
        "profit_currency": "USD",
    },
]

CRYPTO: list[DefaultInstrumentSpec] = [
    {
        "symbol": "BTCUSD",
        "description": "Bitcoin vs US Dollar",
        "asset_class": AssetClass.CRYPTO,
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value_profit": 1,
        "tick_value_loss": 1,
        "contract_size": 1,
        "volume_min": 0.01,
        "volume_max": 20,
        "volume_step": 0.01,
        "profit_currency": "USD",
    },
    {
        "symbol": "ETHUSD",
        "description": "Ethereum vs US Dollar",
        "asset_class": AssetClass.CRYPTO,
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value_profit": 1,
        "tick_value_loss": 1,
        "contract_size": 1,
        "volume_min": 0.01,
        "volume_max": 100,
        "volume_step": 0.01,
        "profit_currency": "USD",
    },
]

INDICES: list[DefaultInstrumentSpec] = [
    {
        "symbol": "US100",
        "description": "Nasdaq 100 Index",
        "asset_class": AssetClass.INDEX,
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value_profit": 1,
        "tick_value_loss": 1,
        "contract_size": 1,
        "volume_min": 0.01,
        "volume_max": 100,
        "volume_step": 0.01,
        "profit_currency": "USD",
    },
]

DEFAULT_INSTRUMENT_SPECS: list[DefaultInstrumentSpec] = [
    *FOREX_MAJORS,
    *FOREX_CROSSES,
    *FOREX_USD_EXOTICS,
    *COMMODITIES,
    *CRYPTO,
    *INDICES,
]
