from datetime import datetime
from typing import TypedDict

from .trade_metrics import MetricTrade, TradeMetricsGroup, group_trade_metrics


class DurationTrade(MetricTrade):
    opened_at: datetime
    closed_at: datetime


class DurationBucket(TypedDict):
    key: str
    label: str
    min_minutes: float
    max_minutes: float | None


DURATION_BUCKETS: list[DurationBucket] = [
    {"key": "under_15m", "label": "< 15 min", "min_minutes": 0.0, "max_minutes": 15.0},
    {"key": "15m_to_1h", "label": "15–60 min", "min_minutes": 15.0, "max_minutes": 60.0},
    {"key": "1h_to_4h", "label": "1–4 hours", "min_minutes": 60.0, "max_minutes": 240.0},
    {"key": "4h_to_24h", "label": "4–24 hours", "min_minutes": 240.0, "max_minutes": 1440.0},
    {"key": "over_24h", "label": "> 24 hours", "min_minutes": 1440.0, "max_minutes": None},
]


def _get_duration_bucket(minutes: float) -> DurationBucket:
    for bucket in DURATION_BUCKETS:
        if bucket["max_minutes"] is None:
            if minutes >= bucket["min_minutes"]:
                return bucket
        elif bucket["min_minutes"] <= minutes < bucket["max_minutes"]:
            return bucket

    return DURATION_BUCKETS[0]


def _empty_bucket(bucket: DurationBucket) -> TradeMetricsGroup:
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


def summarize_duration_analytics(trades: list[DurationTrade]) -> list[TradeMetricsGroup]:
    with_bucket = []
    for trade in trades:
        duration_minutes = (trade["closed_at"] - trade["opened_at"]).total_seconds() / 60.0
        bucket = _get_duration_bucket(duration_minutes)
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
        for bucket in DURATION_BUCKETS
    ]
