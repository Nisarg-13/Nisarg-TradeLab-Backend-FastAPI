from typing import TypedDict

from .pnl import TradePnl
from .win_rate import count_breakeven, count_losses, count_wins


class TradeR(TypedDict):
    net_pnl: float
    realized_r: float | None


def calculate_total_r(trades: list[TradeR]) -> float | None:
    values = [trade["realized_r"] for trade in trades if trade["realized_r"] is not None]

    if not values:
        return None

    return sum(values)


def calculate_average_r(trades: list[TradeR]) -> float | None:
    values = [trade["realized_r"] for trade in trades if trade["realized_r"] is not None]

    if not values:
        return None

    return sum(values) / len(values)


def calculate_money_expectancy(trades: list[TradePnl]) -> float | None:
    if not trades:
        return None

    wins = count_wins(trades)
    losses = count_losses(trades)
    decisive_count = wins + losses

    if decisive_count == 0:
        return 0.0

    win_probability = wins / decisive_count
    loss_probability = losses / decisive_count

    winners = [trade for trade in trades if trade["net_pnl"] > 0]
    losers = [trade for trade in trades if trade["net_pnl"] < 0]

    average_win = (
        sum(trade["net_pnl"] for trade in winners) / len(winners) if winners else 0.0
    )
    average_loss = (
        abs(sum(trade["net_pnl"] for trade in losers) / len(losers)) if losers else 0.0
    )

    breakeven_contribution = 0.0 if count_breakeven(trades) > 0 else 0.0

    return (
        win_probability * average_win
        - loss_probability * average_loss
        + breakeven_contribution
    )


def calculate_r_expectancy(trades: list[TradeR]) -> float | None:
    r_trades = [trade for trade in trades if trade["realized_r"] is not None]

    if not r_trades:
        return None

    wins = [trade for trade in r_trades if trade["realized_r"] > 0]
    losses = [trade for trade in r_trades if trade["realized_r"] < 0]
    decisive_count = len(wins) + len(losses)

    if decisive_count == 0:
        return 0.0

    win_probability = len(wins) / decisive_count
    loss_probability = len(losses) / decisive_count

    average_win = (
        sum(trade["realized_r"] for trade in wins) / len(wins) if wins else 0.0
    )
    average_loss = (
        abs(sum(trade["realized_r"] for trade in losses) / len(losses))
        if losses
        else 0.0
    )

    return win_probability * average_win - loss_probability * average_loss
