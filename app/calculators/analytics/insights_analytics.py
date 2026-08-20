from datetime import datetime
from typing import Callable, Literal, TypedDict

from .sessions import TRADING_SESSION_LABELS, TradingSession, get_trading_session
from .time_analytics import summarize_time_analytics
from .timezone import get_zoned_date_parts
from .trade_metrics import MetricTrade, TradeMetricsGroup, group_trade_metrics, summarize_trade_metrics
from .win_rate import calculate_win_rate

CHART_TIMEFRAME_LABELS: dict[str, str] = {
    "M1": "1 minute",
    "M5": "5 minutes",
    "M15": "15 minutes",
    "M30": "30 minutes",
    "H1": "1 hour",
    "H4": "4 hours",
    "D1": "Daily",
    "W1": "Weekly",
    "NOT_SET": "Not set",
}

TIMEFRAME_ORDER = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]


class ReviewRef(TypedDict, total=False):
    plan_compliance: str | None
    pre_trade_plan: str | None
    post_trade_plan: str | None
    what_went_well: str | None
    what_went_wrong: str | None
    confidence_score: int | None


class AssociationRef(TypedDict):
    id: str
    name: str


class InsightsTrade(MetricTrade):
    symbol: str
    opened_at: datetime
    chart_timeframe: str | None
    strategies: list[AssociationRef]
    tags: list[AssociationRef]
    mistakes: list[AssociationRef]
    review: ReviewRef | None


class SessionSymbolRow(TypedDict):
    session: str
    session_label: str
    symbol: str
    trade_count: int
    net_pnl: float
    total_r: float | None
    win_rate: float | None
    average_r: float | None
    sample_confidence: TradeMetricsGroup["sample_confidence"]


class TimeframeOutcome(TypedDict):
    key: str
    label: str
    wins: int
    losses: int
    breakeven: int
    win_rate: float | None
    net_pnl: float
    trade_count: int


class PlanComplianceBreakdown(TypedDict):
    key: str
    label: str
    followed: int
    partially_followed: int
    did_not_follow: int
    not_reviewed: int
    followed_win_rate: float | None
    not_followed_win_rate: float | None


class JournalCoverage(TypedDict):
    closed_trades: int
    with_chart_timeframe: int
    with_pre_trade_plan: int
    with_post_trade_plan: int
    with_what_went_well: int
    with_what_went_wrong: int
    with_plan_compliance: int
    with_entry_criteria: int
    with_strategies: int
    with_mistakes_tagged: int


class InsightsHighlights(TypedDict):
    best_hour: TradeMetricsGroup | None
    worst_hour: TradeMetricsGroup | None
    best_session: TradeMetricsGroup | None
    worst_session: TradeMetricsGroup | None
    best_day_of_week: TradeMetricsGroup | None
    worst_day_of_week: TradeMetricsGroup | None
    best_symbol: TradeMetricsGroup | None
    worst_symbol: TradeMetricsGroup | None
    best_timeframe: TradeMetricsGroup | None
    worst_timeframe: TradeMetricsGroup | None


class AssociationTrade(MetricTrade):
    association_id: str
    association_name: str


def _has_text(value: str | None) -> bool:
    if value is None:
        return False
    return bool(value.strip())


def _pick_extreme(
    groups: list[TradeMetricsGroup],
    mode: Literal["best", "worst"],
    min_trades: int = 1,
) -> TradeMetricsGroup | None:
    eligible = [group for group in groups if group["trade_count"] >= min_trades]

    if not eligible:
        return None

    if mode == "best":
        return max(eligible, key=lambda group: group["net_pnl"])

    return min(eligible, key=lambda group: group["net_pnl"])


def _summarize_session_symbols(
    trades: list[InsightsTrade],
    time_zone: str,
) -> list[SessionSymbolRow]:
    with_session = [
        {
            **trade,
            "session": get_trading_session(
                get_zoned_date_parts(trade["opened_at"], time_zone)["hour"]
            ),
        }
        for trade in trades
    ]

    groups: dict[str, list[InsightsTrade]] = {}
    for trade in with_session:
        key = f"{trade['session']}|{trade['symbol']}"
        groups.setdefault(key, []).append(trade)

    results = []
    for key, grouped_trades in groups.items():
        session, symbol = key.split("|", 1)
        metrics = summarize_trade_metrics(key, symbol, grouped_trades)
        results.append(
            {
                "session": session,
                "session_label": TRADING_SESSION_LABELS.get(session, session),
                "symbol": symbol,
                "trade_count": metrics["trade_count"],
                "net_pnl": metrics["net_pnl"],
                "total_r": metrics["total_r"],
                "win_rate": metrics["win_rate"],
                "average_r": metrics["average_r"],
                "sample_confidence": metrics["sample_confidence"],
            }
        )

    results.sort(
        key=lambda row: (row["session_label"], -row["net_pnl"]),
    )
    return results


def _timeframe_sort_index(key: str) -> int:
    if key == "NOT_SET":
        return 9223372036854775807
    try:
        return TIMEFRAME_ORDER.index(key)
    except ValueError:
        return 9223372036854775807


def _summarize_timeframe_outcomes(trades: list[InsightsTrade]) -> list[TimeframeOutcome]:
    groups: dict[str, list[InsightsTrade]] = {}
    for trade in trades:
        key = trade.get("chart_timeframe") or "NOT_SET"
        groups.setdefault(key, []).append(trade)

    results = []
    for key, grouped_trades in groups.items():
        wins = sum(1 for trade in grouped_trades if trade["net_pnl"] > 0)
        losses = sum(1 for trade in grouped_trades if trade["net_pnl"] < 0)
        breakeven = sum(1 for trade in grouped_trades if trade["net_pnl"] == 0)

        results.append(
            {
                "key": key,
                "label": CHART_TIMEFRAME_LABELS.get(key, key),
                "wins": wins,
                "losses": losses,
                "breakeven": breakeven,
                "win_rate": calculate_win_rate(grouped_trades),
                "net_pnl": sum(trade["net_pnl"] for trade in grouped_trades),
                "trade_count": len(grouped_trades),
            }
        )

    results.sort(key=lambda row: _timeframe_sort_index(row["key"]))
    return results


def _summarize_journal_coverage(trades: list[InsightsTrade]) -> JournalCoverage:
    def review_field(trade: InsightsTrade, field: str) -> str | None:
        review = trade.get("review")
        if review is None:
            return None
        return review.get(field)

    return {
        "closed_trades": len(trades),
        "with_chart_timeframe": sum(1 for trade in trades if trade.get("chart_timeframe")),
        "with_pre_trade_plan": sum(
            1 for trade in trades if _has_text(review_field(trade, "pre_trade_plan"))
        ),
        "with_post_trade_plan": sum(
            1 for trade in trades if _has_text(review_field(trade, "post_trade_plan"))
        ),
        "with_what_went_well": sum(
            1 for trade in trades if _has_text(review_field(trade, "what_went_well"))
        ),
        "with_what_went_wrong": sum(
            1 for trade in trades if _has_text(review_field(trade, "what_went_wrong"))
        ),
        "with_plan_compliance": sum(
            1 for trade in trades if review_field(trade, "plan_compliance")
        ),
        "with_entry_criteria": sum(1 for trade in trades if trade.get("tags")),
        "with_strategies": sum(1 for trade in trades if trade.get("strategies")),
        "with_mistakes_tagged": sum(1 for trade in trades if trade.get("mistakes")),
    }


def _summarize_plan_compliance_by_timeframe(
    trades: list[InsightsTrade],
) -> list[PlanComplianceBreakdown]:
    def plan_compliance(trade: InsightsTrade) -> str | None:
        review = trade.get("review")
        if review is None:
            return None
        return review.get("plan_compliance")

    groups: dict[str, list[InsightsTrade]] = {}
    for trade in trades:
        key = trade.get("chart_timeframe") or "NOT_SET"
        groups.setdefault(key, []).append(trade)

    results = []
    for key, grouped_trades in groups.items():
        followed = [
            trade
            for trade in grouped_trades
            if plan_compliance(trade) == "FOLLOWED"
        ]
        not_followed = [
            trade
            for trade in grouped_trades
            if plan_compliance(trade)
            in {"DID_NOT_FOLLOW", "PARTIALLY_FOLLOWED"}
        ]

        results.append(
            {
                "key": key,
                "label": CHART_TIMEFRAME_LABELS.get(key, key),
                "followed": len(followed),
                "partially_followed": sum(
                    1
                    for trade in grouped_trades
                    if plan_compliance(trade) == "PARTIALLY_FOLLOWED"
                ),
                "did_not_follow": sum(
                    1
                    for trade in grouped_trades
                    if plan_compliance(trade) == "DID_NOT_FOLLOW"
                ),
                "not_reviewed": sum(
                    1
                    for trade in grouped_trades
                    if not plan_compliance(trade)
                    or plan_compliance(trade) == "NOT_REVIEWED"
                ),
                "followed_win_rate": calculate_win_rate(followed),
                "not_followed_win_rate": calculate_win_rate(not_followed),
            }
        )

    results.sort(key=lambda row: row["label"])
    return results


def _flatten_associations(
    trades: list[InsightsTrade],
    get_items: Callable[[InsightsTrade], list[AssociationRef]],
) -> list[AssociationTrade]:
    rows: list[AssociationTrade] = []

    for trade in trades:
        for item in get_items(trade):
            rows.append(
                {
                    "net_pnl": trade["net_pnl"],
                    "realized_r": trade["realized_r"],
                    "association_id": item["id"],
                    "association_name": item["name"],
                }
            )

    return rows


def _summarize_association_groups(
    trades: list[InsightsTrade],
    get_items: Callable[[InsightsTrade], list[AssociationRef]],
) -> list[TradeMetricsGroup]:
    flattened = _flatten_associations(trades, get_items)

    return group_trade_metrics(
        flattened,
        lambda trade: trade["association_id"],
        lambda _key, grouped_trades: grouped_trades[0]["association_name"],
    )


def _sort_timeframe_groups(groups: list[TradeMetricsGroup]) -> list[TradeMetricsGroup]:
    return sorted(groups, key=lambda group: _timeframe_sort_index(group["key"]))


def summarize_insights_analytics(
    trades: list[InsightsTrade],
    time_zone: str,
) -> dict:
    time_analytics = summarize_time_analytics(trades, time_zone)
    symbols = group_trade_metrics(
        trades,
        lambda trade: trade["symbol"],
        lambda key, _grouped: key,
    )
    timeframes = _sort_timeframe_groups(
        group_trade_metrics(
            trades,
            lambda trade: trade.get("chart_timeframe") or "NOT_SET",
            lambda key, _grouped: CHART_TIMEFRAME_LABELS.get(key, key),
        )
    )

    winning_trades = [trade for trade in trades if trade["net_pnl"] > 0]
    losing_trades = [trade for trade in trades if trade["net_pnl"] < 0]

    highlights: InsightsHighlights = {
        "best_hour": _pick_extreme(time_analytics["hours"], "best"),
        "worst_hour": _pick_extreme(time_analytics["hours"], "worst"),
        "best_session": _pick_extreme(time_analytics["sessions"], "best"),
        "worst_session": _pick_extreme(time_analytics["sessions"], "worst"),
        "best_day_of_week": _pick_extreme(time_analytics["days_of_week"], "best"),
        "worst_day_of_week": _pick_extreme(time_analytics["days_of_week"], "worst"),
        "best_symbol": _pick_extreme(symbols, "best"),
        "worst_symbol": _pick_extreme(symbols, "worst"),
        "best_timeframe": _pick_extreme(timeframes, "best"),
        "worst_timeframe": _pick_extreme(timeframes, "worst"),
    }

    return {
        "highlights": highlights,
        "session_symbols": _summarize_session_symbols(trades, time_zone),
        "timeframes": timeframes,
        "timeframe_outcomes": _summarize_timeframe_outcomes(trades),
        "journal_coverage": _summarize_journal_coverage(trades),
        "plan_compliance_by_timeframe": _summarize_plan_compliance_by_timeframe(trades),
        "winning_entry_criteria": _summarize_association_groups(
            winning_trades,
            lambda trade: trade.get("tags", []),
        ),
        "losing_entry_criteria": _summarize_association_groups(
            losing_trades,
            lambda trade: trade.get("tags", []),
        ),
        "winning_strategies": _summarize_association_groups(
            winning_trades,
            lambda trade: trade.get("strategies", []),
        ),
        "losing_strategies": _summarize_association_groups(
            losing_trades,
            lambda trade: trade.get("strategies", []),
        ),
        "losing_mistakes": _summarize_association_groups(
            losing_trades,
            lambda trade: trade.get("mistakes", []),
        ),
    }
