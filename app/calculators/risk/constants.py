DEFAULT_RISK_SETTINGS = {
    "maxRiskPerTradePercentage": 2,
    "maxDailyRiskPercentage": 5,
    "maxDailyLossPercentage": 5,
    "maxOpenRiskPercentage": 10,
    "maxTradesPerDay": 5,
    "maxConsecutiveLosses": 3,
    "strictMode": False,
}


def _get_default_instrument_specs():
    from app.data.default_instruments import DEFAULT_INSTRUMENT_SPECS

    return DEFAULT_INSTRUMENT_SPECS


def find_catalog_instrument(symbol: str):
    return next(
        (
            instrument
            for instrument in _get_default_instrument_specs()
            if instrument["symbol"] == symbol.upper()
        ),
        None,
    )


def list_catalog_instruments() -> list[dict[str, str | int | None]]:
    return [
        {
            "symbol": instrument["symbol"],
            "description": instrument.get("description"),
            "assetClass": instrument["asset_class"].value,
            "digits": instrument["digits"],
            "point": str(instrument["point"]),
            "tickSize": str(instrument["tick_size"]),
            "tickValueProfit": str(instrument["tick_value_profit"]),
            "tickValueLoss": str(instrument["tick_value_loss"]),
            "contractSize": str(instrument["contract_size"]),
            "volumeMin": str(instrument["volume_min"]),
            "volumeMax": str(instrument["volume_max"]),
            "volumeStep": str(instrument["volume_step"]),
            "baseCurrency": instrument.get("base_currency"),
            "profitCurrency": instrument.get("profit_currency"),
        }
        for instrument in _get_default_instrument_specs()
    ]
