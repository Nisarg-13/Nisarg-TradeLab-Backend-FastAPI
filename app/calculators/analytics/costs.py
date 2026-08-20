from typing import TypedDict


class TradeCosts(TypedDict):
    commission: float
    swap: float
    fees: float


def calculate_total_commission(trades: list[TradeCosts]) -> float:
    return sum(trade["commission"] for trade in trades)


def calculate_total_swap(trades: list[TradeCosts]) -> float:
    return sum(trade["swap"] for trade in trades)


def calculate_total_fees(trades: list[TradeCosts]) -> float:
    return sum(trade["fees"] for trade in trades)


def calculate_total_trading_costs(trades: list[TradeCosts]) -> float:
    return (
        calculate_total_commission(trades)
        + calculate_total_swap(trades)
        + calculate_total_fees(trades)
    )
