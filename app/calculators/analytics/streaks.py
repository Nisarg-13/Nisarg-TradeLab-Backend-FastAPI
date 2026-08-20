from datetime import datetime
from typing import Literal, TypedDict


class StreakTrade(TypedDict):
    net_pnl: float
    closed_at: datetime


class StreakResult(TypedDict):
    longest_winning_streak: int
    longest_losing_streak: int
    current_winning_streak: int
    current_losing_streak: int


Outcome = Literal["win", "loss", "breakeven"]


def _get_outcome(net_pnl: float) -> Outcome:
    if net_pnl > 0:
        return "win"
    if net_pnl < 0:
        return "loss"
    return "breakeven"


def calculate_streaks(trades: list[StreakTrade]) -> StreakResult:
    sorted_trades = sorted(trades, key=lambda trade: trade["closed_at"])

    longest_winning_streak = 0
    longest_losing_streak = 0
    current_winning_streak = 0
    current_losing_streak = 0
    running_win_streak = 0
    running_loss_streak = 0

    for trade in sorted_trades:
        outcome = _get_outcome(trade["net_pnl"])

        if outcome == "win":
            running_win_streak += 1
            running_loss_streak = 0
            longest_winning_streak = max(longest_winning_streak, running_win_streak)
        elif outcome == "loss":
            running_loss_streak += 1
            running_win_streak = 0
            longest_losing_streak = max(longest_losing_streak, running_loss_streak)

    for index in range(len(sorted_trades) - 1, -1, -1):
        outcome = _get_outcome(sorted_trades[index]["net_pnl"])

        if outcome == "breakeven":
            continue

        if outcome == "win":
            if current_losing_streak > 0:
                break
            current_winning_streak += 1
        else:
            if current_winning_streak > 0:
                break
            current_losing_streak += 1

    return {
        "longest_winning_streak": longest_winning_streak,
        "longest_losing_streak": longest_losing_streak,
        "current_winning_streak": current_winning_streak,
        "current_losing_streak": current_losing_streak,
    }
