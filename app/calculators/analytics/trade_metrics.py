from datetime import datetime
from typing import Callable, TypedDict, TypeVar

from .expectancy import (
    calculate_average_r,
    calculate_money_expectancy,
    calculate_r_expectancy,
    calculate_total_r,
)
from .pnl import calculate_net_pnl, calculate_profit_factor
from .sample_confidence import SampleConfidence, get_sample_confidence
from .win_rate import calculate_win_rate


class MetricTrade(TypedDict):
    net_pnl: float
    realized_r: float | None


class TradeMetricsGroup(TypedDict):
    key: str
    label: str
    trade_count: int
    net_pnl: float
    total_r: float | None
    win_rate: float | None
    average_r: float | None
    money_expectancy: float | None
    r_expectancy: float | None
    profit_factor: float | None
    sample_confidence: SampleConfidence


T = TypeVar("T", bound=MetricTrade)


def summarize_trade_metrics(
    key: str,
    label: str,
    trades: list[MetricTrade],
) -> TradeMetricsGroup:
    total_r = calculate_total_r(trades)

    return {
        "key": key,
        "label": label,
        "trade_count": len(trades),
        "net_pnl": calculate_net_pnl(trades),
        "total_r": total_r,
        "win_rate": calculate_win_rate(trades),
        "average_r": calculate_average_r(trades),
        "money_expectancy": calculate_money_expectancy(trades),
        "r_expectancy": calculate_r_expectancy(trades),
        "profit_factor": calculate_profit_factor(trades),
        "sample_confidence": get_sample_confidence(len(trades)),
    }


def summarize_metric_trades(trades: list[MetricTrade]) -> TradeMetricsGroup:
    return summarize_trade_metrics("all", "All trades", trades)


def group_trade_metrics(
    trades: list[T],
    get_key: Callable[[T], str],
    get_label: Callable[[str, list[T]], str],
) -> list[TradeMetricsGroup]:
    groups: dict[str, list[T]] = {}

    for trade in trades:
        key = get_key(trade)
        groups.setdefault(key, []).append(trade)

    return sorted(
        (
            summarize_trade_metrics(key, get_label(key, grouped_trades), grouped_trades)
            for key, grouped_trades in groups.items()
        ),
        key=lambda group: group["net_pnl"],
        reverse=True,
    )
