from datetime import datetime, timezone
from typing import TypedDict


class CalendarTrade(TypedDict, total=False):
    closed_at: datetime
    net_pnl: float
    realized_r: float | None


class CalendarDay(TypedDict):
    date: str
    pnl: float
    r: float
    trade_count: int


def build_calendar(closed_trades: list[CalendarTrade]) -> list[CalendarDay]:
    by_day: dict[str, dict[str, float | int]] = {}

    for trade in closed_trades:
        closed_at = trade["closed_at"]
        day = closed_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        current = by_day.get(day, {"pnl": 0.0, "r": 0.0, "trade_count": 0})

        current["pnl"] = float(current["pnl"]) + trade["net_pnl"]
        current["r"] = float(current["r"]) + (
            trade["realized_r"] if trade["realized_r"] is not None else 0.0
        )
        current["trade_count"] = int(current["trade_count"]) + 1
        by_day[day] = current

    return [
        {
            "date": date,
            "pnl": float(values["pnl"]),
            "r": float(values["r"]),
            "trade_count": int(values["trade_count"]),
        }
        for date, values in sorted(by_day.items(), key=lambda item: item[0])
    ]
