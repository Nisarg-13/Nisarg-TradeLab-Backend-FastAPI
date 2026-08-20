from typing import TypedDict


class ClosedTradePnl(TypedDict):
    net_pnl: float


def calculate_win_rate(trades: list[ClosedTradePnl]) -> float | None:
    decisive = [trade for trade in trades if trade["net_pnl"] != 0]

    if not decisive:
        return None

    wins = sum(1 for trade in decisive if trade["net_pnl"] > 0)
    return wins / len(decisive)


def count_wins(trades: list[ClosedTradePnl]) -> int:
    return sum(1 for trade in trades if trade["net_pnl"] > 0)


def count_losses(trades: list[ClosedTradePnl]) -> int:
    return sum(1 for trade in trades if trade["net_pnl"] < 0)


def count_breakeven(trades: list[ClosedTradePnl]) -> int:
    return sum(1 for trade in trades if trade["net_pnl"] == 0)


def calculate_loss_rate(trades: list[ClosedTradePnl]) -> float | None:
    win_rate = calculate_win_rate(trades)

    if win_rate is None:
        return None

    return 1 - win_rate


def calculate_breakeven_rate(trades: list[ClosedTradePnl]) -> float | None:
    if not trades:
        return None

    return count_breakeven(trades) / len(trades)
