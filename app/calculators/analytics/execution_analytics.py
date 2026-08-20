from datetime import datetime
import math
from typing import Literal, TypedDict

from .holding_time import calculate_average_holding_time_minutes
from .planned_rr_analytics import summarize_planned_vs_realized

Direction = Literal["LONG", "SHORT"]


class ExecutionEvent(TypedDict):
    type: str
    previous_value: str | None
    new_value: str | None


class ExecutionRecord(TypedDict, total=False):
    average_entry_price: float
    average_exit_price: float | None
    opened_at: datetime
    closed_at: datetime | None
    direction: Direction
    initial_stop_loss: float | None
    planned_rr: float | None
    realized_r: float | None
    mfe_r: float | None
    entry_count: int
    exit_count: int
    partial_exit_count: int
    events: list[ExecutionEvent]


class SlModificationStats(TypedDict):
    sl_modification_count: int
    moved_to_breakeven_count: int
    widened_sl_count: int
    reduced_risk_count: int
    increased_risk_count: int


class ExecutionAnalyticsSummary(SlModificationStats):
    trade_count: int
    average_entry_price: float | None
    average_exit_price: float | None
    entry_count: int
    exit_count: int
    partial_exit_count: int
    average_hold_time_minutes: float | None
    planned_vs_realized: dict
    tp_modification_count: int
    mfe_available_count: int
    average_exit_efficiency: float | None


def _parse_number(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None

    try:
        parsed = float(value)
    except ValueError:
        return None

    return parsed if math.isfinite(parsed) else None


def _is_stop_widened(direction: Direction, previous_stop: float, new_stop: float) -> bool:
    if direction == "LONG":
        return new_stop < previous_stop

    return new_stop > previous_stop


def _summarize_sl_modifications(
    direction: Direction,
    events: list[ExecutionEvent],
) -> SlModificationStats:
    sl_modification_count = 0
    moved_to_breakeven_count = 0
    widened_sl_count = 0
    reduced_risk_count = 0
    increased_risk_count = 0

    for event in events:
        if event["type"] == "BREAKEVEN":
            moved_to_breakeven_count += 1
            continue

        if event["type"] != "SL_CHANGED":
            continue

        previous_stop = _parse_number(event.get("previous_value"))
        new_stop = _parse_number(event.get("new_value"))

        if previous_stop is None or new_stop is None:
            sl_modification_count += 1
            continue

        sl_modification_count += 1

        if previous_stop == new_stop:
            continue

        if _is_stop_widened(direction, previous_stop, new_stop):
            widened_sl_count += 1
            increased_risk_count += 1
        else:
            reduced_risk_count += 1

    return {
        "sl_modification_count": sl_modification_count,
        "moved_to_breakeven_count": moved_to_breakeven_count,
        "widened_sl_count": widened_sl_count,
        "reduced_risk_count": reduced_risk_count,
        "increased_risk_count": increased_risk_count,
    }


def summarize_execution_analytics(trades: list[ExecutionRecord]) -> ExecutionAnalyticsSummary:
    closed_trades = [trade for trade in trades if trade.get("closed_at") is not None]

    average_entry_price = (
        sum(trade["average_entry_price"] for trade in closed_trades) / len(closed_trades)
        if closed_trades
        else None
    )

    trades_with_exit = [
        trade for trade in closed_trades if trade.get("average_exit_price") is not None
    ]
    average_exit_price = (
        sum(trade["average_exit_price"] for trade in trades_with_exit)
        / len(trades_with_exit)
        if trades_with_exit
        else None
    )

    entry_count = sum(trade.get("entry_count", 0) for trade in trades)
    exit_count = sum(trade.get("exit_count", 0) for trade in trades)
    partial_exit_count = sum(trade.get("partial_exit_count", 0) for trade in trades)

    average_hold_time_minutes = calculate_average_holding_time_minutes(
        [
            {"opened_at": trade["opened_at"], "closed_at": trade["closed_at"]}
            for trade in closed_trades
        ]
    )

    planned_vs_realized = summarize_planned_vs_realized(
        [
            {
                "net_pnl": 0.0,
                "realized_r": trade.get("realized_r"),
                "planned_rr": trade.get("planned_rr"),
            }
            for trade in closed_trades
        ]
    )

    sl_stats = {
        "sl_modification_count": 0,
        "tp_modification_count": 0,
        "moved_to_breakeven_count": 0,
        "widened_sl_count": 0,
        "reduced_risk_count": 0,
        "increased_risk_count": 0,
    }

    for trade in closed_trades:
        stats = _summarize_sl_modifications(trade["direction"], trade.get("events", []))
        sl_stats["sl_modification_count"] += stats["sl_modification_count"]
        sl_stats["tp_modification_count"] += sum(
            1 for event in trade.get("events", []) if event["type"] == "TP_CHANGED"
        )
        sl_stats["moved_to_breakeven_count"] += stats["moved_to_breakeven_count"]
        sl_stats["widened_sl_count"] += stats["widened_sl_count"]
        sl_stats["reduced_risk_count"] += stats["reduced_risk_count"]
        sl_stats["increased_risk_count"] += stats["increased_risk_count"]

    mfe_available_trades = [
        trade
        for trade in closed_trades
        if trade.get("mfe_r") is not None
        and trade["mfe_r"] > 0
        and trade.get("realized_r") is not None
    ]
    exit_efficiency_values = [
        trade["realized_r"] / trade["mfe_r"] for trade in mfe_available_trades
    ]
    average_exit_efficiency = (
        sum(exit_efficiency_values) / len(exit_efficiency_values)
        if exit_efficiency_values
        else None
    )

    return {
        "trade_count": len(closed_trades),
        "average_entry_price": average_entry_price,
        "average_exit_price": average_exit_price,
        "entry_count": entry_count,
        "exit_count": exit_count,
        "partial_exit_count": partial_exit_count,
        "average_hold_time_minutes": average_hold_time_minutes,
        "planned_vs_realized": planned_vs_realized,
        **sl_stats,
        "mfe_available_count": len(mfe_available_trades),
        "average_exit_efficiency": average_exit_efficiency,
    }
