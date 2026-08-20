from typing import TypedDict

from .sample_confidence import SampleConfidence, get_sample_confidence

DEFAULT_CAPTURE_THRESHOLD = 0.75


class EarlyWinnerExitTrade(TypedDict):
    net_pnl: float
    realized_r: float | None
    planned_rr: float | None


class EarlyWinnerExitSummary(TypedDict):
    winner_count: int
    early_exit_count: int
    early_exit_rate: float | None
    average_planned_r: float | None
    average_realized_r: float | None
    average_capture_ratio: float | None
    sample_confidence: SampleConfidence


def summarize_early_winner_exits(
    trades: list[EarlyWinnerExitTrade],
    capture_threshold: float = DEFAULT_CAPTURE_THRESHOLD,
) -> EarlyWinnerExitSummary:
    winners = [
        trade
        for trade in trades
        if trade["net_pnl"] > 0
        and trade.get("planned_rr") is not None
        and trade["planned_rr"] > 0
        and trade.get("realized_r") is not None
    ]

    if not winners:
        return {
            "winner_count": 0,
            "early_exit_count": 0,
            "early_exit_rate": None,
            "average_planned_r": None,
            "average_realized_r": None,
            "average_capture_ratio": None,
            "sample_confidence": get_sample_confidence(0),
        }

    capture_ratios = [trade["realized_r"] / trade["planned_rr"] for trade in winners]
    early_exits = [
        trade
        for trade, ratio in zip(winners, capture_ratios, strict=True)
        if ratio < capture_threshold
    ]

    average_planned_r = sum(trade["planned_rr"] for trade in winners) / len(winners)
    average_realized_r = sum(trade["realized_r"] for trade in winners) / len(winners)
    average_capture_ratio = sum(capture_ratios) / len(capture_ratios)

    return {
        "winner_count": len(winners),
        "early_exit_count": len(early_exits),
        "early_exit_rate": len(early_exits) / len(winners),
        "average_planned_r": average_planned_r,
        "average_realized_r": average_realized_r,
        "average_capture_ratio": average_capture_ratio,
        "sample_confidence": get_sample_confidence(len(winners)),
    }
