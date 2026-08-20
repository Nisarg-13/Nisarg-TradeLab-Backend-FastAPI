from typing import TypedDict


class TradePnl(TypedDict):
    net_pnl: float


def calculate_net_pnl(trades: list[TradePnl]) -> float:
    return sum(trade["net_pnl"] for trade in trades)


def calculate_gross_profit(trades: list[TradePnl]) -> float:
    return sum(trade["net_pnl"] for trade in trades if trade["net_pnl"] > 0)


def calculate_gross_loss(trades: list[TradePnl]) -> float:
    return sum(trade["net_pnl"] for trade in trades if trade["net_pnl"] < 0)


def calculate_profit_factor(trades: list[TradePnl]) -> float | None:
    gross_profit = calculate_gross_profit(trades)
    gross_loss = calculate_gross_loss(trades)

    if gross_loss == 0:
        return None

    return gross_profit / abs(gross_loss)


def calculate_average_winner(trades: list[TradePnl]) -> float | None:
    winners = [trade for trade in trades if trade["net_pnl"] > 0]

    if not winners:
        return None

    return sum(trade["net_pnl"] for trade in winners) / len(winners)


def calculate_average_loser(trades: list[TradePnl]) -> float | None:
    losers = [trade for trade in trades if trade["net_pnl"] < 0]

    if not losers:
        return None

    return sum(trade["net_pnl"] for trade in losers) / len(losers)


def calculate_largest_winner(trades: list[TradePnl]) -> float | None:
    winners = [trade for trade in trades if trade["net_pnl"] > 0]

    if not winners:
        return None

    return max(trade["net_pnl"] for trade in winners)


def calculate_average_win_loss_ratio(trades: list[TradePnl]) -> float | None:
    average_winner = calculate_average_winner(trades)
    average_loser = calculate_average_loser(trades)

    if average_winner is None or average_loser is None or average_loser == 0:
        return None

    return average_winner / abs(average_loser)


def calculate_largest_loser(trades: list[TradePnl]) -> float | None:
    losers = [trade for trade in trades if trade["net_pnl"] < 0]

    if not losers:
        return None

    return min(trade["net_pnl"] for trade in losers)
