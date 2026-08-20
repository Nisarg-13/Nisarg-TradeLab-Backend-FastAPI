from .direction import calculate_price_distance
from .types import TradeDirection


def calculate_risk_reward(
    direction: TradeDirection,
    entry_price: float,
    stop_loss: float,
    take_profit: float | None = None,
    tick_size: float | None = None,
) -> float | None:
    if take_profit is None:
        return None

    risk = calculate_price_distance(entry_price, stop_loss, tick_size)
    reward = calculate_reward_distance(
        direction,
        entry_price,
        take_profit,
        tick_size,
    )

    if risk <= 0 or reward <= 0:
        return None

    return reward / risk


def calculate_reward_distance(
    direction: TradeDirection,
    entry_price: float,
    take_profit: float,
    tick_size: float | None = None,
) -> float:
    raw_distance = (
        take_profit - entry_price
        if direction == "LONG"
        else entry_price - take_profit
    )

    if tick_size is not None and tick_size > 0:
        ticks = round(raw_distance / tick_size)
        return ticks * tick_size

    return raw_distance
