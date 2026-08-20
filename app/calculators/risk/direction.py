from .types import TradeDirection


def validate_stop_loss(
    direction: TradeDirection,
    entry_price: float,
    stop_loss: float,
) -> bool:
    return stop_loss < entry_price if direction == "LONG" else stop_loss > entry_price


def validate_take_profit(
    direction: TradeDirection,
    entry_price: float,
    take_profit: float,
) -> bool:
    return (
        take_profit > entry_price
        if direction == "LONG"
        else take_profit < entry_price
    )


def calculate_price_distance(
    entry_price: float,
    stop_loss: float,
    tick_size: float | None = None,
) -> float:
    distance = abs(entry_price - stop_loss)

    if tick_size is not None and tick_size > 0:
        ticks = round(distance / tick_size)
        return ticks * tick_size

    return distance
