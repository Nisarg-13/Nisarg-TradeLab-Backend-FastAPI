from typing import TypedDict

from .expectancy import (
    calculate_average_r,
    calculate_money_expectancy,
    calculate_r_expectancy,
)
from .pnl import calculate_net_pnl, calculate_profit_factor
from .sample_confidence import SampleConfidence, get_sample_confidence
from .win_rate import calculate_win_rate, count_losses, count_wins


class RiskStatTrade(TypedDict):
    net_pnl: float
    realized_r: float | None
    initial_risk_percentage: float | None


class RiskStatGroup(TypedDict):
    label: str
    risk_percentage_min: float | None
    risk_percentage_max: float | None
    trade_count: int
    win_count: int
    loss_count: int
    net_pnl: float
    win_rate: float | None
    average_r: float | None
    money_expectancy: float | None
    r_expectancy: float | None
    profit_factor: float | None
    sample_confidence: SampleConfidence


RISK_BUCKETS: list[dict[str, str | float | None]] = [
    {"label": "Unknown risk %", "min": None, "max": None},
    {"label": "≤ 0.50%", "min": 0.0, "max": 0.5},
    {"label": "0.51% – 1.00%", "min": 0.51, "max": 1.0},
    {"label": "1.01% – 2.00%", "min": 1.01, "max": 2.0},
    {"label": "> 2.00%", "min": 2.01, "max": None},
]


def _matches_bucket(
    risk_percentage: float | None,
    minimum: float | None,
    maximum: float | None,
) -> bool:
    if minimum is None and maximum is None:
        return risk_percentage is None

    if risk_percentage is None:
        return False

    if minimum is not None and risk_percentage < minimum:
        return False

    if maximum is not None and risk_percentage > maximum:
        return False

    return True


def _summarize_bucket(
    label: str,
    minimum: float | None,
    maximum: float | None,
    trades: list[RiskStatTrade],
) -> RiskStatGroup:
    return {
        "label": label,
        "risk_percentage_min": minimum,
        "risk_percentage_max": maximum,
        "trade_count": len(trades),
        "win_count": count_wins(trades),
        "loss_count": count_losses(trades),
        "net_pnl": calculate_net_pnl(trades),
        "win_rate": calculate_win_rate(trades),
        "average_r": calculate_average_r(trades),
        "money_expectancy": calculate_money_expectancy(trades),
        "r_expectancy": calculate_r_expectancy(trades),
        "profit_factor": calculate_profit_factor(trades),
        "sample_confidence": get_sample_confidence(len(trades)),
    }


def summarize_risk_stats(trades: list[RiskStatTrade]) -> list[RiskStatGroup]:
    return [
        group
        for bucket in RISK_BUCKETS
        if (
            group := _summarize_bucket(
                str(bucket["label"]),
                bucket["min"] if bucket["min"] is not None else None,
                bucket["max"] if bucket["max"] is not None else None,
                [
                    trade
                    for trade in trades
                    if _matches_bucket(
                        trade.get("initial_risk_percentage"),
                        bucket["min"] if isinstance(bucket["min"], (int, float)) else None,
                        bucket["max"] if isinstance(bucket["max"], (int, float)) else None,
                    )
                ],
            )
        ).get("trade_count", 0)
        > 0
        or group["risk_percentage_min"] is None
    ]
