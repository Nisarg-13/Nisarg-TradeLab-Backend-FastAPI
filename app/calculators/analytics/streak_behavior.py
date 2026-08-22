from datetime import datetime
from typing import Literal, TypedDict

from .trade_metrics import MetricTrade, TradeMetricsGroup, empty_trade_metrics_group, group_trade_metrics

StreakBucketKey = Literal["normal", "after_1", "after_2", "after_3_plus"]


class StreakBehaviorTrade(MetricTrade):
    closed_at: datetime


class StreakBucketDefinition(TypedDict):
    key: StreakBucketKey
    label: str


LOSS_BUCKET_DEFINITIONS: list[dict] = [
    {"key": "normal", "label": "Normal / no loss streak", "matches": lambda s: s == 0},
    {"key": "after_1", "label": "After 1 loss", "matches": lambda s: s == 1},
    {"key": "after_2", "label": "After 2 consecutive losses", "matches": lambda s: s == 2},
    {
        "key": "after_3_plus",
        "label": "After 3+ consecutive losses",
        "matches": lambda s: s >= 3,
    },
]

WIN_BUCKET_DEFINITIONS: list[dict] = [
    {"key": "normal", "label": "Normal / no win streak", "matches": lambda s: s == 0},
    {"key": "after_1", "label": "After 1 win", "matches": lambda s: s == 1},
    {"key": "after_2", "label": "After 2 consecutive wins", "matches": lambda s: s == 2},
    {
        "key": "after_3_plus",
        "label": "After 3+ consecutive wins",
        "matches": lambda s: s >= 3,
    },
]


def _count_preceding_streak(
    sorted_trades: list[StreakBehaviorTrade],
    index: int,
    streak_type: Literal["win", "loss"],
) -> int:
    if index == 0:
        return 0

    streak = 0

    for cursor in range(index - 1, -1, -1):
        trade = sorted_trades[cursor]
        is_win = trade["net_pnl"] > 0
        is_loss = trade["net_pnl"] < 0

        if streak_type == "loss":
            if not is_loss:
                break
            streak += 1
            continue

        if not is_win:
            break

        streak += 1

    return streak


def _empty_bucket(definition: dict) -> TradeMetricsGroup:
    return empty_trade_metrics_group(definition["key"], definition["label"])


def _summarize_streak_buckets(
    trades: list[StreakBehaviorTrade],
    streak_type: Literal["win", "loss"],
) -> list[TradeMetricsGroup]:
    definitions = LOSS_BUCKET_DEFINITIONS if streak_type == "loss" else WIN_BUCKET_DEFINITIONS
    sorted_trades = sorted(trades, key=lambda trade: trade["closed_at"])

    with_streak = [
        {
            **trade,
            "streak": _count_preceding_streak(sorted_trades, index, streak_type),
        }
        for index, trade in enumerate(sorted_trades)
    ]

    grouped = group_trade_metrics(
        with_streak,
        lambda trade: next(
            (definition["key"] for definition in definitions if definition["matches"](trade["streak"])),
            "normal",
        ),
        lambda key, _grouped: next(
            (definition["label"] for definition in definitions if definition["key"] == key),
            key,
        ),
    )

    return [
        next((group for group in grouped if group["key"] == definition["key"]), _empty_bucket(definition))
        for definition in definitions
    ]


def summarize_after_loss_buckets(trades: list[StreakBehaviorTrade]) -> list[TradeMetricsGroup]:
    return _summarize_streak_buckets(trades, "loss")


def summarize_after_win_buckets(trades: list[StreakBehaviorTrade]) -> list[TradeMetricsGroup]:
    return _summarize_streak_buckets(trades, "win")
