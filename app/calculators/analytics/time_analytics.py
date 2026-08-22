from datetime import datetime
from typing import Callable, TypedDict

from .sessions import (
    TRADING_SESSION_LABELS,
    TRADING_SESSION_ORDER,
    format_two_hour_window_label,
    get_trading_session,
    get_two_hour_window_start,
)
from .timezone import DAY_OF_WEEK_LABELS, format_hour_label, get_zoned_date_parts
from .trade_metrics import MetricTrade, group_trade_metrics


class TimeAnalyticsTrade(MetricTrade):
    opened_at: datetime
    trade_id: str
    symbol: str


class TimeGroupEntry(TypedDict):
    trade_id: str
    symbol: str
    opened_at: datetime


class TimeAnalyticsResult(TypedDict):
    hours: list
    two_hour_windows: list
    days_of_week: list
    months: list
    sessions: list


def index_time_group_entries(
    trades: list[TimeAnalyticsTrade],
    time_zone: str,
    bucket_for_hour: Callable[[int], int],
) -> dict[str, list[TimeGroupEntry]]:
    entries_by_key: dict[str, list[TimeGroupEntry]] = {}

    for trade in trades:
        parts = get_zoned_date_parts(trade["opened_at"], time_zone)
        key = str(bucket_for_hour(parts["hour"]))
        entries_by_key.setdefault(key, []).append(
            {
                "trade_id": trade["trade_id"],
                "symbol": trade["symbol"],
                "opened_at": trade["opened_at"],
            }
        )

    for entries in entries_by_key.values():
        entries.sort(key=lambda entry: entry["opened_at"])

    return entries_by_key


def summarize_time_analytics(
    trades: list[TimeAnalyticsTrade],
    time_zone: str,
) -> TimeAnalyticsResult:
    with_parts = []
    for trade in trades:
        parts = get_zoned_date_parts(trade["opened_at"], time_zone)
        with_parts.append(
            {
                **trade,
                "parts": parts,
                "session": get_trading_session(parts["hour"]),
            }
        )

    hours = group_trade_metrics(
        with_parts,
        lambda trade: str(trade["parts"]["hour"]),
        lambda key, _grouped: format_hour_label(int(key)),
    )
    hours.sort(key=lambda group: int(group["key"]))

    days_of_week = group_trade_metrics(
        with_parts,
        lambda trade: str(trade["parts"]["day_of_week"]),
        lambda key, _grouped: DAY_OF_WEEK_LABELS[int(key)],
    )
    days_of_week.sort(key=lambda group: int(group["key"]))

    months = group_trade_metrics(
        with_parts,
        lambda trade: trade["parts"]["month_key"],
        lambda key, grouped_trades: grouped_trades[0]["parts"]["month_label"]
        if grouped_trades
        else key,
    )
    months.sort(key=lambda group: group["key"])

    sessions = group_trade_metrics(
        with_parts,
        lambda trade: trade["session"],
        lambda key, _grouped: TRADING_SESSION_LABELS[key],
    )
    sessions.sort(
        key=lambda group: (
            TRADING_SESSION_ORDER.index(group["key"])
            if group["key"] in TRADING_SESSION_ORDER
            else len(TRADING_SESSION_ORDER)
        )
    )

    two_hour_windows = group_trade_metrics(
        with_parts,
        lambda trade: str(get_two_hour_window_start(trade["parts"]["hour"])),
        lambda key, _grouped: format_two_hour_window_label(int(key)),
    )
    two_hour_windows.sort(key=lambda group: int(group["key"]))

    return {
        "hours": hours,
        "two_hour_windows": two_hour_windows,
        "days_of_week": days_of_week,
        "months": months,
        "sessions": sessions,
    }
