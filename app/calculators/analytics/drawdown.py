from datetime import datetime, timedelta, timezone
from typing import TypedDict


class EquityPoint(TypedDict):
    balance: float


class DrawdownResult(TypedDict):
    max_drawdown_amount: float
    max_drawdown_percentage: float
    current_drawdown_amount: float
    current_drawdown_percentage: float


class EquityCurvePoint(TypedDict):
    date: str
    balance: float
    cumulative_pnl: float
    cumulative_r: float


class ClosedTradeForEquity(TypedDict, total=False):
    closed_at: datetime
    opened_at: datetime
    net_pnl: float
    realized_r: float | None


def calculate_drawdown(
    points: list[EquityPoint],
    starting_balance: float,
) -> DrawdownResult:
    if not points or starting_balance <= 0:
        return {
            "max_drawdown_amount": 0.0,
            "max_drawdown_percentage": 0.0,
            "current_drawdown_amount": 0.0,
            "current_drawdown_percentage": 0.0,
        }

    peak = starting_balance
    max_drawdown_amount = 0.0
    max_drawdown_percentage = 0.0

    for point in points:
        peak = max(peak, point["balance"])
        drawdown_amount = peak - point["balance"]
        drawdown_percentage = (drawdown_amount / peak) * 100 if peak > 0 else 0.0

        max_drawdown_amount = max(max_drawdown_amount, drawdown_amount)
        max_drawdown_percentage = max(max_drawdown_percentage, drawdown_percentage)

    latest_balance = points[-1]["balance"] if points else starting_balance
    current_peak = max(
        (point["balance"] for point in points),
        default=starting_balance,
    )
    current_peak = max(current_peak, starting_balance)
    current_drawdown_amount = max(0.0, current_peak - latest_balance)
    current_drawdown_percentage = (
        (current_drawdown_amount / current_peak) * 100 if current_peak > 0 else 0.0
    )

    return {
        "max_drawdown_amount": max_drawdown_amount,
        "max_drawdown_percentage": max_drawdown_percentage,
        "current_drawdown_amount": current_drawdown_amount,
        "current_drawdown_percentage": current_drawdown_percentage,
    }


def build_equity_curve(
    closed_trades: list[ClosedTradeForEquity],
    starting_balance: float,
) -> list[EquityCurvePoint]:
    sorted_trades = sorted(
        closed_trades,
        key=lambda trade: trade["closed_at"],
    )

    cumulative_pnl = 0.0
    cumulative_r = 0.0
    points: list[EquityCurvePoint] = []

    if sorted_trades:
        first_trade = sorted_trades[0]
        opened_at = first_trade.get("opened_at")
        closed_at = first_trade["closed_at"]

        if opened_at is not None and opened_at <= closed_at:
            anchor_date = opened_at
        else:
            anchor_date = closed_at - timedelta(milliseconds=1)

        points.append(
            {
                "date": anchor_date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "balance": starting_balance,
                "cumulative_pnl": 0.0,
                "cumulative_r": 0.0,
            }
        )

    for trade in sorted_trades:
        cumulative_pnl += trade["net_pnl"]
        cumulative_r += trade["realized_r"] if trade["realized_r"] is not None else 0.0

        closed_at = trade["closed_at"]
        points.append(
            {
                "date": closed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "balance": starting_balance + cumulative_pnl,
                "cumulative_pnl": cumulative_pnl,
                "cumulative_r": cumulative_r,
            }
        )

    return points
