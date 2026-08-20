from typing import TypedDict

from .trade_metrics import MetricTrade, TradeMetricsGroup, group_trade_metrics


class PlannedRrTrade(MetricTrade):
    planned_rr: float | None


class PlannedRrBucket(TypedDict):
    key: str
    label: str
    min: float
    max: float | None


PLANNED_RR_BUCKETS: list[PlannedRrBucket] = [
    {"key": "under_1", "label": "< 1R", "min": 0.0, "max": 1.0},
    {"key": "1_to_1_49", "label": "1.0 – 1.49R", "min": 1.0, "max": 1.5},
    {"key": "1_5_to_1_99", "label": "1.5 – 1.99R", "min": 1.5, "max": 2.0},
    {"key": "2_to_2_49", "label": "2.0 – 2.49R", "min": 2.0, "max": 2.5},
    {"key": "2_5_to_2_99", "label": "2.5 – 2.99R", "min": 2.5, "max": 3.0},
    {"key": "3_plus", "label": "3R+", "min": 3.0, "max": None},
]


class PlannedVsRealizedSummary(TypedDict):
    trade_count: int
    average_planned_r: float | None
    average_realized_r: float | None
    average_realized_winner_r: float | None
    target_achievement_rate: float | None


def _get_planned_rr_bucket(planned_rr: float) -> PlannedRrBucket:
    for bucket in PLANNED_RR_BUCKETS:
        if bucket["max"] is None:
            if planned_rr >= bucket["min"]:
                return bucket
        elif bucket["min"] <= planned_rr < bucket["max"]:
            return bucket

    return PLANNED_RR_BUCKETS[0]


def _empty_bucket(bucket: PlannedRrBucket) -> TradeMetricsGroup:
    return {
        "key": bucket["key"],
        "label": bucket["label"],
        "trade_count": 0,
        "net_pnl": 0.0,
        "total_r": None,
        "win_rate": None,
        "average_r": None,
        "money_expectancy": None,
        "r_expectancy": None,
        "profit_factor": None,
        "sample_confidence": "INSUFFICIENT",
    }


def summarize_planned_rr_analytics(trades: list[PlannedRrTrade]) -> list[TradeMetricsGroup]:
    with_bucket = []
    for trade in trades:
        planned_rr = trade.get("planned_rr")
        if planned_rr is None or planned_rr <= 0:
            continue
        bucket = _get_planned_rr_bucket(planned_rr)
        with_bucket.append(
            {
                **trade,
                "bucket_key": bucket["key"],
                "bucket_label": bucket["label"],
            }
        )

    grouped = group_trade_metrics(
        with_bucket,
        lambda trade: trade["bucket_key"],
        lambda key, grouped_trades: grouped_trades[0]["bucket_label"]
        if grouped_trades
        else key,
    )

    return [
        next((group for group in grouped if group["key"] == bucket["key"]), _empty_bucket(bucket))
        for bucket in PLANNED_RR_BUCKETS
    ]


def summarize_planned_vs_realized(trades: list[PlannedRrTrade]) -> PlannedVsRealizedSummary:
    with_planned = [
        trade
        for trade in trades
        if trade.get("planned_rr") is not None and trade["planned_rr"] > 0
    ]

    winners = [trade for trade in with_planned if trade["net_pnl"] > 0]
    with_realized_r = [trade for trade in with_planned if trade.get("realized_r") is not None]

    average_planned_r = (
        sum(trade["planned_rr"] for trade in with_planned) / len(with_planned)
        if with_planned
        else None
    )

    average_realized_r = (
        sum(trade["realized_r"] for trade in with_realized_r) / len(with_realized_r)
        if with_realized_r
        else None
    )

    winners_with_r = [trade for trade in winners if trade.get("realized_r") is not None]
    average_realized_winner_r = (
        sum(trade["realized_r"] for trade in winners_with_r) / len(winners_with_r)
        if winners_with_r
        else None
    )

    capture_ratios = [
        trade["realized_r"] / trade["planned_rr"]
        for trade in winners
        if trade.get("realized_r") is not None
        and trade.get("planned_rr") is not None
        and trade["planned_rr"] > 0
    ]

    target_achievement_rate = (
        sum(1 for ratio in capture_ratios if ratio >= 1) / len(capture_ratios)
        if capture_ratios
        else None
    )

    return {
        "trade_count": len(with_planned),
        "average_planned_r": average_planned_r,
        "average_realized_r": average_realized_r,
        "average_realized_winner_r": average_realized_winner_r,
        "target_achievement_rate": target_achievement_rate,
    }
