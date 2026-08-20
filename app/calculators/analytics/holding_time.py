from datetime import datetime
from typing import TypedDict


class HoldingTimeTrade(TypedDict):
    opened_at: datetime
    closed_at: datetime


def calculate_average_holding_time_minutes(
    trades: list[HoldingTimeTrade],
) -> float | None:
    if not trades:
        return None

    total_minutes = sum(
        (trade["closed_at"] - trade["opened_at"]).total_seconds() / 60.0
        for trade in trades
    )

    return total_minutes / len(trades)


def calculate_median_holding_time_minutes(
    trades: list[HoldingTimeTrade],
) -> float | None:
    if not trades:
        return None

    durations = sorted(
        (trade["closed_at"] - trade["opened_at"]).total_seconds() / 60.0
        for trade in trades
    )

    middle = len(durations) // 2

    if len(durations) % 2 == 0:
        return (durations[middle - 1] + durations[middle]) / 2.0

    return durations[middle]
