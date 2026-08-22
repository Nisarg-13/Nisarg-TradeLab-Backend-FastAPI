from datetime import datetime
from typing import TypedDict

from .group_performance import summarize_closed_trades
from .sample_confidence import SampleConfidence, get_sample_confidence


class AfterLossesTrade(TypedDict):
    net_pnl: float
    realized_r: float | None
    closed_at: datetime


class AfterLossesSummary(TypedDict):
    loss_streak_threshold: int
    trade_count: int
    win_count: int
    loss_count: int
    net_pnl: float
    win_rate: float | None
    average_r: float | None
    r_expectancy: float | None
    sample_confidence: SampleConfidence
    baseline_trade_count: int
    baseline_win_count: int
    baseline_loss_count: int
    baseline_win_rate: float | None
    baseline_net_pnl: float


def select_trades_after_loss_streak(
    trades: list[AfterLossesTrade],
    loss_streak_threshold: int,
) -> list[AfterLossesTrade]:
    if loss_streak_threshold < 1:
        return []

    sorted_trades = sorted(trades, key=lambda trade: trade["closed_at"])
    selected: list[AfterLossesTrade] = []

    for index in range(loss_streak_threshold, len(sorted_trades)):
        previous = sorted_trades[index - loss_streak_threshold : index]

        if all(trade["net_pnl"] < 0 for trade in previous):
            selected.append(sorted_trades[index])

    return selected


def summarize_after_losses_performance(
    trades: list[AfterLossesTrade],
    loss_streak_threshold: int = 2,
) -> AfterLossesSummary:
    selected = select_trades_after_loss_streak(trades, loss_streak_threshold)
    records = [
        {
            "symbol": "after-losses",
            "strategies": [],
            "net_pnl": trade["net_pnl"],
            "realized_r": trade["realized_r"],
        }
        for trade in selected
    ]

    metrics = summarize_closed_trades(records)
    baseline = summarize_closed_trades(
        [
            {
                "symbol": "baseline",
                "strategies": [],
                "net_pnl": trade["net_pnl"],
                "realized_r": trade["realized_r"],
            }
            for trade in trades
        ]
    )

    return {
        "loss_streak_threshold": loss_streak_threshold,
        "trade_count": len(selected),
        "win_count": metrics["win_count"],
        "loss_count": metrics["loss_count"],
        "net_pnl": metrics["net_pnl"],
        "win_rate": metrics["win_rate"],
        "average_r": metrics["average_r"],
        "r_expectancy": metrics["r_expectancy"],
        "sample_confidence": get_sample_confidence(len(selected)),
        "baseline_trade_count": len(trades),
        "baseline_win_count": baseline["win_count"],
        "baseline_loss_count": baseline["loss_count"],
        "baseline_win_rate": baseline["win_rate"],
        "baseline_net_pnl": baseline["net_pnl"],
    }
