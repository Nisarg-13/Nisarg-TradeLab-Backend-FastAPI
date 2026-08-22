from typing import TypedDict

from .trade_metrics import MetricTrade, summarize_trade_metrics


class MistakeAnalyticsTrade(MetricTrade):
    mistake_id: str
    mistake_name: str


class MistakeAnalyticsResult(TypedDict):
    mistake_id: str
    mistake_name: str
    trade_count: int
    win_count: int
    loss_count: int
    net_pnl: float
    total_r: float | None
    average_r: float | None
    win_rate: float | None
    money_expectancy: float | None
    r_expectancy: float | None
    profit_factor: float | None
    sample_confidence: str


def summarize_mistake_analytics(
    trades: list[MistakeAnalyticsTrade],
) -> list[MistakeAnalyticsResult]:
    groups: dict[str, list[MistakeAnalyticsTrade]] = {}

    for trade in trades:
        groups.setdefault(trade["mistake_id"], []).append(trade)

    results = []
    for mistake_id, grouped_trades in groups.items():
        metrics = summarize_trade_metrics(
            mistake_id,
            grouped_trades[0].get("mistake_name", mistake_id),
            grouped_trades,
        )
        results.append(
            {
                "mistake_id": mistake_id,
                "mistake_name": grouped_trades[0].get("mistake_name", mistake_id),
                "trade_count": metrics["trade_count"],
                "win_count": metrics["win_count"],
                "loss_count": metrics["loss_count"],
                "net_pnl": metrics["net_pnl"],
                "total_r": metrics["total_r"],
                "average_r": metrics["average_r"],
                "win_rate": metrics["win_rate"],
                "money_expectancy": metrics["money_expectancy"],
                "r_expectancy": metrics["r_expectancy"],
                "profit_factor": metrics["profit_factor"],
                "sample_confidence": metrics["sample_confidence"],
            }
        )

    results.sort(key=lambda entry: entry["trade_count"], reverse=True)
    return results
