from datetime import datetime
from typing import TypedDict

from .sessions import TRADING_SESSION_LABELS, TRADING_SESSION_ORDER, get_trading_session
from .timezone import DAY_OF_WEEK_LABELS, get_zoned_date_parts
from .trade_metrics import MetricTrade, summarize_trade_metrics


class SessionDashboardTrade(MetricTrade):
    opened_at: datetime


class SessionWeekdayCell(TypedDict):
    session: str
    session_label: str
    day_of_week: int
    day_label: str
    trade_count: int
    win_count: int
    loss_count: int
    net_pnl: float
    win_rate: float | None
    money_expectancy: float | None


def _empty_cell(session: str, day_of_week: int) -> SessionWeekdayCell:
    return {
        "session": session,
        "session_label": TRADING_SESSION_LABELS[session],
        "day_of_week": day_of_week,
        "day_label": DAY_OF_WEEK_LABELS[day_of_week],
        "trade_count": 0,
        "win_count": 0,
        "loss_count": 0,
        "net_pnl": 0.0,
        "win_rate": None,
        "money_expectancy": None,
    }


def summarize_session_weekday_matrix(
    trades: list[SessionDashboardTrade],
    time_zone: str,
) -> list[SessionWeekdayCell]:
    with_meta = []
    for trade in trades:
        parts = get_zoned_date_parts(trade["opened_at"], time_zone)
        with_meta.append(
            {
                **trade,
                "session": get_trading_session(parts["hour"]),
                "day_of_week": parts["day_of_week"],
            }
        )

    cells: list[SessionWeekdayCell] = []
    for session in TRADING_SESSION_ORDER:
        for day_of_week in range(7):
            grouped = [
                trade
                for trade in with_meta
                if trade["session"] == session and trade["day_of_week"] == day_of_week
            ]

            if not grouped:
                cells.append(_empty_cell(session, day_of_week))
                continue

            metrics = summarize_trade_metrics(
                f"{session}-{day_of_week}",
                DAY_OF_WEEK_LABELS[day_of_week],
                grouped,
            )
            cells.append(
                {
                    "session": session,
                    "session_label": TRADING_SESSION_LABELS[session],
                    "day_of_week": day_of_week,
                    "day_label": DAY_OF_WEEK_LABELS[day_of_week],
                    "trade_count": metrics["trade_count"],
                    "win_count": metrics["win_count"],
                    "loss_count": metrics["loss_count"],
                    "net_pnl": metrics["net_pnl"],
                    "win_rate": metrics["win_rate"],
                    "money_expectancy": metrics["money_expectancy"],
                }
            )

    return cells
