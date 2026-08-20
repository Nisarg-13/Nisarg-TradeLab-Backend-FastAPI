import math
import sys

InstrumentPricing = dict[str, float]


def _get_decimal_places(value: float) -> int:
    text = f"{value:.15f}".rstrip("0").rstrip(".")
    parts = text.split(".")
    return len(parts[1]) if len(parts) > 1 else 0


def _count_ticks(price_distance: float, tick_size: float) -> int:
    if price_distance <= 0 or tick_size <= 0:
        return 0

    return round(price_distance / tick_size)


def _uses_forex_tick_override(
    instrument: InstrumentPricing,
    explicit_tick_value: float,
) -> bool:
    monetary_tick_value = instrument["contractSize"] * instrument["tickSize"]

    return (
        instrument["contractSize"] == 100_000
        and explicit_tick_value != monetary_tick_value
    )


def _price_units_per_tick(tick_size: float) -> float:
    return 10 ** _get_decimal_places(tick_size)


def _calculate_linear_monetary_per_lot(
    tick_count: int,
    contract_size: float,
    tick_size: float,
) -> float:
    return (tick_count * contract_size) / _price_units_per_tick(tick_size)


def _calculate_monetary_per_lot(
    price_distance: float,
    instrument: InstrumentPricing,
    tick_value: float,
    entry_price: float | None = None,
) -> float:
    tick_count = _count_ticks(price_distance, instrument["tickSize"])

    if tick_count <= 0:
        return 0

    if _uses_forex_tick_override(instrument, tick_value):
        if entry_price is not None and entry_price > 0:
            return (
                _calculate_linear_monetary_per_lot(
                    tick_count,
                    instrument["contractSize"],
                    instrument["tickSize"],
                )
                / entry_price
            )

        return tick_count * tick_value

    return _calculate_linear_monetary_per_lot(
        tick_count,
        instrument["contractSize"],
        instrument["tickSize"],
    )


def calculate_loss_per_lot(
    price_distance: float,
    instrument: InstrumentPricing,
    entry_price: float | None = None,
) -> float:
    return _calculate_monetary_per_lot(
        price_distance,
        instrument,
        instrument["tickValueLoss"],
        entry_price,
    )


def calculate_profit_per_lot(
    reward_distance: float,
    instrument: InstrumentPricing,
    entry_price: float | None = None,
) -> float:
    return _calculate_monetary_per_lot(
        reward_distance,
        instrument,
        instrument["tickValueProfit"],
        entry_price,
    )


def calculate_raw_volume(risk_amount: float, loss_per_lot: float) -> float:
    if risk_amount <= 0 or loss_per_lot <= 0:
        return 0

    return risk_amount / loss_per_lot


def round_volume_down(raw_volume: float, volume_step: float) -> float:
    if raw_volume <= 0 or volume_step <= 0:
        return 0

    decimals = _get_decimal_places(volume_step)
    scale = 10**decimals
    step_units = volume_step * scale
    raw_units = raw_volume * scale
    steps = math.floor((raw_units + sys.float_info.epsilon) / step_units)
    rounded = (steps * step_units) / scale

    return float(f"{rounded:.{decimals}f}")


def clamp_volume(
    volume: float,
    instrument: dict[str, float],
) -> float:
    if volume <= 0 or volume < instrument["volumeMin"]:
        return 0

    return min(volume, instrument["volumeMax"])
