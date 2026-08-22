from datetime import datetime
from typing import Literal, TypedDict

from .expectancy import calculate_average_r, calculate_money_expectancy
from .pnl import calculate_net_pnl
from .timezone import get_zoned_date_parts
from .trade_metrics import MetricTrade
from .win_rate import calculate_win_rate, count_losses, count_wins

HeatmapMetric = Literal["pnl", "averageR", "expectancy", "winRate", "tradeCount"]


class HeatmapTrade(MetricTrade):
    opened_at: datetime


class HeatmapCell(TypedDict):
    day_of_week: int
    hour: int
    trade_count: int
    win_count: int
    loss_count: int
    net_pnl: float
    average_r: float | None
    win_rate: float | None
    value: float


def _metric_value(metric: HeatmapMetric, trades: list[MetricTrade]) -> float:
    if metric == "pnl":
        return calculate_net_pnl(trades)
    if metric == "averageR":
        return calculate_average_r(trades) or 0.0
    if metric == "expectancy":
        return calculate_money_expectancy(trades) or 0.0
    if metric == "winRate":
        return calculate_win_rate(trades) or 0.0
    return float(len(trades))


def build_heatmap(
    trades: list[HeatmapTrade],
    time_zone: str,
    metric: HeatmapMetric,
) -> list[HeatmapCell]:
    buckets: dict[str, list[MetricTrade]] = {}

    for trade in trades:
        parts = get_zoned_date_parts(trade["opened_at"], time_zone)
        key = f"{parts['day_of_week']}:{parts['hour']}"
        buckets.setdefault(key, []).append(trade)

    cells: list[HeatmapCell] = []

    for day_of_week in range(7):
        for hour in range(24):
            grouped_trades = buckets.get(f"{day_of_week}:{hour}", [])

            cells.append(
                {
                    "day_of_week": day_of_week,
                    "hour": hour,
                    "trade_count": len(grouped_trades),
                    "win_count": count_wins(grouped_trades),
                    "loss_count": count_losses(grouped_trades),
                    "net_pnl": calculate_net_pnl(grouped_trades),
                    "average_r": calculate_average_r(grouped_trades),
                    "win_rate": calculate_win_rate(grouped_trades),
                    "value": _metric_value(metric, grouped_trades),
                }
            )

    return cells
