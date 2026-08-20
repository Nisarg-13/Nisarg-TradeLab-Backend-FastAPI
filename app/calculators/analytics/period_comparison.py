from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

from .costs import calculate_total_trading_costs
from .drawdown import build_equity_curve, calculate_drawdown
from .expectancy import calculate_total_r
from .holding_time import calculate_average_holding_time_minutes
from .plan_compliance import (
    PlanComplianceStatus,
    is_followed_plan_compliance,
    is_reviewed_plan_compliance,
)
from .sample_confidence import SampleConfidence
from .trade_metrics import MetricTrade, TradeMetricsGroup, summarize_metric_trades

PeriodComparisonMode = Literal[
    "LATEST_20_VS_PREVIOUS_20",
    "FIRST_50_VS_LATEST_50",
    "THIS_MONTH_VS_LAST_MONTH",
    "CUSTOM",
]


class RollingTrade(MetricTrade):
    closed_at: datetime
    opened_at: datetime
    has_mistake: bool
    plan_compliance: PlanComplianceStatus | None
    initial_risk_percentage: float | None
    commission: float
    swap: float
    fees: float


class RollingPoint(TypedDict):
    index: int
    closed_at: str
    net_pnl: float
    window_trade_count: int
    window_win_rate: float | None
    window_average_r: float | None
    window_net_pnl: float


class RollingPerformanceSummary(TypedDict):
    window_size: int
    current_window: TradeMetricsGroup
    previous_window: TradeMetricsGroup
    points: list[RollingPoint]


class PeriodMetricsSummary(TypedDict):
    trade_count: int
    net_pnl: float
    total_r: float | None
    win_rate: float | None
    average_r: float | None
    money_expectancy: float | None
    profit_factor: float | None
    max_drawdown_amount: float
    max_drawdown_percentage: float
    mistake_rate: float | None
    plan_compliance_rate: float | None
    average_risk_percentage: float | None
    average_holding_time_minutes: float | None
    total_trading_costs: float
    sample_confidence: SampleConfidence


class PeriodComparisonDelta(TypedDict):
    win_rate: float | None
    average_r: float | None
    money_expectancy: float | None
    profit_factor: float | None
    mistake_rate: float | None
    plan_compliance_rate: float | None
    max_drawdown_amount: float | None
    max_drawdown_percentage: float | None
    net_pnl: float | None
    total_r: float | None
    average_risk_percentage: float | None
    average_holding_time_minutes: float | None
    total_trading_costs: float | None


class ComparisonWindows(TypedDict):
    period_a: list[RollingTrade]
    period_b: list[RollingTrade]
    period_a_label: str
    period_b_label: str


class CustomPeriodRange(TypedDict, total=False):
    period_a_from: datetime
    period_a_to: datetime
    period_b_from: datetime
    period_b_to: datetime


def summarize_rolling_performance(
    trades: list[RollingTrade],
    window_size: int = 20,
) -> RollingPerformanceSummary:
    ordered = sorted(trades, key=lambda trade: trade["closed_at"])
    current_window = ordered[-window_size:]
    previous_window = ordered[-window_size * 2 : -window_size]

    points: list[RollingPoint] = []
    for index, trade in enumerate(ordered):
        window_start = max(0, index - window_size + 1)
        window = ordered[window_start : index + 1]
        summary = summarize_metric_trades(
            [{"net_pnl": item["net_pnl"], "realized_r": item["realized_r"]} for item in window]
        )

        points.append(
            {
                "index": index + 1,
                "closed_at": trade["closed_at"].astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "net_pnl": trade["net_pnl"],
                "window_trade_count": len(window),
                "window_win_rate": summary["win_rate"],
                "window_average_r": summary["average_r"],
                "window_net_pnl": summary["net_pnl"],
            }
        )

    return {
        "window_size": window_size,
        "current_window": summarize_metric_trades(current_window),
        "previous_window": summarize_metric_trades(previous_window),
        "points": points,
    }


def summarize_period_metrics(
    trades: list[RollingTrade],
    starting_balance: float,
) -> PeriodMetricsSummary:
    summary = summarize_metric_trades(trades)
    equity_curve = build_equity_curve(
        [
            {
                "closed_at": trade["closed_at"],
                "net_pnl": trade["net_pnl"],
                "realized_r": trade["realized_r"],
            }
            for trade in trades
        ],
        starting_balance,
    )
    drawdown = calculate_drawdown(equity_curve, starting_balance)

    reviewed = [
        trade for trade in trades if is_reviewed_plan_compliance(trade.get("plan_compliance"))
    ]
    followed = [
        trade for trade in reviewed if is_followed_plan_compliance(trade.get("plan_compliance"))
    ]
    with_mistakes = [trade for trade in trades if trade["has_mistake"]]
    with_risk = [
        trade for trade in trades if trade.get("initial_risk_percentage") is not None
    ]

    return {
        "trade_count": len(trades),
        "net_pnl": summary["net_pnl"],
        "total_r": calculate_total_r(trades),
        "win_rate": summary["win_rate"],
        "average_r": summary["average_r"],
        "money_expectancy": summary["money_expectancy"],
        "profit_factor": summary["profit_factor"],
        "max_drawdown_amount": drawdown["max_drawdown_amount"],
        "max_drawdown_percentage": drawdown["max_drawdown_percentage"],
        "mistake_rate": len(with_mistakes) / len(trades) if trades else None,
        "plan_compliance_rate": len(followed) / len(reviewed) if reviewed else None,
        "average_risk_percentage": (
            sum(trade["initial_risk_percentage"] for trade in with_risk) / len(with_risk)
            if with_risk
            else None
        ),
        "average_holding_time_minutes": calculate_average_holding_time_minutes(
            [{"opened_at": trade["opened_at"], "closed_at": trade["closed_at"]} for trade in trades]
        ),
        "total_trading_costs": calculate_total_trading_costs(
            [
                {
                    "commission": trade["commission"],
                    "swap": trade["swap"],
                    "fees": trade["fees"],
                }
                for trade in trades
            ]
        ),
        "sample_confidence": summary["sample_confidence"],
    }


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None

    return current - previous


def compare_periods(
    period_a: PeriodMetricsSummary,
    period_b: PeriodMetricsSummary,
) -> PeriodComparisonDelta:
    return {
        "win_rate": _delta(period_a["win_rate"], period_b["win_rate"]),
        "average_r": _delta(period_a["average_r"], period_b["average_r"]),
        "money_expectancy": _delta(period_a["money_expectancy"], period_b["money_expectancy"]),
        "profit_factor": _delta(period_a["profit_factor"], period_b["profit_factor"]),
        "mistake_rate": _delta(period_a["mistake_rate"], period_b["mistake_rate"]),
        "plan_compliance_rate": _delta(
            period_a["plan_compliance_rate"],
            period_b["plan_compliance_rate"],
        ),
        "max_drawdown_amount": _delta(
            period_a["max_drawdown_amount"],
            period_b["max_drawdown_amount"],
        ),
        "max_drawdown_percentage": _delta(
            period_a["max_drawdown_percentage"],
            period_b["max_drawdown_percentage"],
        ),
        "net_pnl": _delta(period_a["net_pnl"], period_b["net_pnl"]),
        "total_r": _delta(period_a["total_r"], period_b["total_r"]),
        "average_risk_percentage": _delta(
            period_a["average_risk_percentage"],
            period_b["average_risk_percentage"],
        ),
        "average_holding_time_minutes": _delta(
            period_a["average_holding_time_minutes"],
            period_b["average_holding_time_minutes"],
        ),
        "total_trading_costs": _delta(
            period_a["total_trading_costs"],
            period_b["total_trading_costs"],
        ),
    }


def resolve_comparison_windows(
    trades: list[RollingTrade],
    mode: PeriodComparisonMode,
    custom: CustomPeriodRange | None = None,
) -> ComparisonWindows:
    ordered = sorted(trades, key=lambda trade: trade["closed_at"])

    if mode == "LATEST_20_VS_PREVIOUS_20":
        return {
            "period_a": ordered[-20:],
            "period_b": ordered[-40:-20],
            "period_a_label": "Latest 20 trades",
            "period_b_label": "Previous 20 trades",
        }

    if mode == "FIRST_50_VS_LATEST_50":
        return {
            "period_a": ordered[-50:],
            "period_b": ordered[:50],
            "period_a_label": "Latest 50 trades",
            "period_b_label": "First 50 trades",
        }

    if mode == "THIS_MONTH_VS_LAST_MONTH":
        now = datetime.now(timezone.utc)
        current_month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 1:
            previous_month_start = datetime(now.year - 1, 12, 1, tzinfo=timezone.utc)
        else:
            previous_month_start = datetime(now.year, now.month - 1, 1, tzinfo=timezone.utc)
        previous_month_end = current_month_start - timedelta(milliseconds=1)

        return {
            "period_a": [trade for trade in ordered if trade["closed_at"] >= current_month_start],
            "period_b": [
                trade
                for trade in ordered
                if previous_month_start <= trade["closed_at"] <= previous_month_end
            ],
            "period_a_label": "This month",
            "period_b_label": "Last month",
        }

    if custom is None:
        custom = {}

    period_a_from = custom.get("period_a_from")
    period_a_to = custom.get("period_a_to")
    period_b_from = custom.get("period_b_from")
    period_b_to = custom.get("period_b_to")

    if not period_a_from or not period_a_to or not period_b_from or not period_b_to:
        raise ValueError("Custom period comparison requires both date ranges.")

    return {
        "period_a": [
            trade
            for trade in ordered
            if period_a_from <= trade["closed_at"] <= period_a_to
        ],
        "period_b": [
            trade
            for trade in ordered
            if period_b_from <= trade["closed_at"] <= period_b_to
        ],
        "period_a_label": "Period A",
        "period_b_label": "Period B",
    }
