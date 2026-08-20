from typing import Literal, TypedDict

from .expectancy import (
    calculate_average_r,
    calculate_money_expectancy,
    calculate_r_expectancy,
)
from .pnl import calculate_net_pnl, calculate_profit_factor
from .sample_confidence import SampleConfidence, get_sample_confidence
from .win_rate import calculate_win_rate

PlanComplianceStatus = Literal[
    "FOLLOWED",
    "PARTIALLY_FOLLOWED",
    "DID_NOT_FOLLOW",
    "NOT_REVIEWED",
]


class PlanComplianceTrade(TypedDict):
    net_pnl: float
    realized_r: float | None
    plan_compliance: PlanComplianceStatus | None


class PlanComplianceGroup(TypedDict):
    label: str
    plan_compliance: PlanComplianceStatus
    trade_count: int
    net_pnl: float
    win_rate: float | None
    average_r: float | None
    money_expectancy: float | None
    r_expectancy: float | None
    profit_factor: float | None
    sample_confidence: SampleConfidence


GROUP_DEFINITIONS: list[dict[str, str]] = [
    {"plan_compliance": "FOLLOWED", "label": "Followed plan"},
    {"plan_compliance": "PARTIALLY_FOLLOWED", "label": "Partially followed plan"},
    {"plan_compliance": "DID_NOT_FOLLOW", "label": "Did not follow plan"},
    {"plan_compliance": "NOT_REVIEWED", "label": "Not reviewed"},
]


def _summarize_group(
    label: str,
    plan_compliance: PlanComplianceStatus,
    trades: list[PlanComplianceTrade],
) -> PlanComplianceGroup:
    return {
        "label": label,
        "plan_compliance": plan_compliance,
        "trade_count": len(trades),
        "net_pnl": calculate_net_pnl(trades),
        "win_rate": calculate_win_rate(trades),
        "average_r": calculate_average_r(trades),
        "money_expectancy": calculate_money_expectancy(trades),
        "r_expectancy": calculate_r_expectancy(trades),
        "profit_factor": calculate_profit_factor(trades),
        "sample_confidence": get_sample_confidence(len(trades)),
    }


def summarize_plan_compliance(
    trades: list[PlanComplianceTrade],
) -> list[PlanComplianceGroup]:
    return [
        _summarize_group(
            definition["label"],
            definition["plan_compliance"],
            [
                trade
                for trade in trades
                if (trade.get("plan_compliance") or "NOT_REVIEWED")
                == definition["plan_compliance"]
            ],
        )
        for definition in GROUP_DEFINITIONS
    ]


def is_reviewed_plan_compliance(
    plan_compliance: PlanComplianceStatus | None,
) -> bool:
    return plan_compliance is not None and plan_compliance != "NOT_REVIEWED"


def is_followed_plan_compliance(
    plan_compliance: PlanComplianceStatus | None,
) -> bool:
    return plan_compliance == "FOLLOWED"
