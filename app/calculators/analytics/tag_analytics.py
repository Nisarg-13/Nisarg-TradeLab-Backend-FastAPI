from typing import TypedDict

from .trade_metrics import MetricTrade, summarize_trade_metrics


class TagAnalyticsTrade(MetricTrade):
    tag_id: str
    tag_name: str


class TagAnalyticsResult(TypedDict):
    tag_id: str
    tag_name: str
    trade_count: int
    net_pnl: float
    total_r: float | None
    average_r: float | None
    win_rate: float | None
    money_expectancy: float | None
    r_expectancy: float | None
    profit_factor: float | None
    sample_confidence: str


def summarize_tag_analytics(trades: list[TagAnalyticsTrade]) -> list[TagAnalyticsResult]:
    groups: dict[str, list[TagAnalyticsTrade]] = {}

    for trade in trades:
        groups.setdefault(trade["tag_id"], []).append(trade)

    results = []
    for tag_id, grouped_trades in groups.items():
        metrics = summarize_trade_metrics(
            tag_id,
            grouped_trades[0].get("tag_name", tag_id),
            grouped_trades,
        )
        results.append(
            {
                "tag_id": tag_id,
                "tag_name": grouped_trades[0].get("tag_name", tag_id),
                "trade_count": metrics["trade_count"],
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

    results.sort(key=lambda entry: entry["net_pnl"], reverse=True)
    return results
