from __future__ import annotations

from typing import Any

TOP_N = 8

MetricRow = dict[str, Any]


def _top_by_trade_count(rows: list[MetricRow], limit: int = TOP_N) -> list[MetricRow]:
    return sorted(rows, key=lambda row: float(row.get("tradeCount") or 0), reverse=True)[:limit]


def _top_by_abs_net_pnl(rows: list[MetricRow], limit: int = TOP_N) -> list[MetricRow]:
    return sorted(
        rows,
        key=lambda row: abs(float(row.get("netPnl") or 0)),
        reverse=True,
    )[:limit]


def _slim_summary(summary: dict[str, Any]) -> dict[str, Any]:
    rest = dict(summary)
    rest.pop("equityCurve", None)
    rest.pop("calendar", None)
    return rest


def _slim_time_analytics(time_analytics: dict[str, Any]) -> dict[str, Any]:
    return {
        "sessions": (
            _top_by_trade_count(time_analytics["sessions"])
            if isinstance(time_analytics.get("sessions"), list)
            else []
        ),
        "hours": (
            _top_by_trade_count(time_analytics["hours"])
            if isinstance(time_analytics.get("hours"), list)
            else []
        ),
        "daysOfWeek": (
            time_analytics["daysOfWeek"]
            if isinstance(time_analytics.get("daysOfWeek"), list)
            else []
        ),
        "twoHourWindows": (
            _top_by_trade_count(time_analytics["twoHourWindows"], 6)
            if isinstance(time_analytics.get("twoHourWindows"), list)
            else []
        ),
    }


def _slim_insights(insights: dict[str, Any]) -> dict[str, Any]:
    return {
        "highlights": insights.get("highlights") or {},
        "journalCoverage": insights.get("journalCoverage") or {},
        "timeframeOutcomes": (
            insights["timeframeOutcomes"]
            if isinstance(insights.get("timeframeOutcomes"), list)
            else []
        ),
        "sessionSymbols": (
            _top_by_abs_net_pnl(insights["sessionSymbols"], 16)
            if isinstance(insights.get("sessionSymbols"), list)
            else []
        ),
        "winningEntryCriteria": (
            insights["winningEntryCriteria"][:TOP_N]
            if isinstance(insights.get("winningEntryCriteria"), list)
            else []
        ),
        "losingEntryCriteria": (
            insights["losingEntryCriteria"][:TOP_N]
            if isinstance(insights.get("losingEntryCriteria"), list)
            else []
        ),
        "winningStrategies": (
            insights["winningStrategies"][:TOP_N]
            if isinstance(insights.get("winningStrategies"), list)
            else []
        ),
        "losingStrategies": (
            insights["losingStrategies"][:TOP_N]
            if isinstance(insights.get("losingStrategies"), list)
            else []
        ),
        "losingMistakes": (
            insights["losingMistakes"][:TOP_N]
            if isinstance(insights.get("losingMistakes"), list)
            else []
        ),
    }


def slim_context_for_llm(context: dict[str, Any]) -> dict[str, Any]:
    """Reduce token usage and avoid oversized OpenAI requests on production."""
    psychology = context.get("psychology") or {}
    direction = context.get("direction") or {}
    behavior = context.get("behavior") or {}

    return {
        "sampleSize": context.get("sampleSize"),
        "sampleConfidence": context.get("sampleConfidence"),
        "timezone": context.get("timezone"),
        "summary": _slim_summary(context.get("summary") or {}),
        "instruments": _top_by_abs_net_pnl(context.get("instruments") or []),
        "strategies": _top_by_abs_net_pnl(context.get("strategies") or []),
        "tags": _top_by_abs_net_pnl(context.get("tags") or []),
        "mistakes": _top_by_trade_count(context.get("mistakes") or []),
        "planCompliance": context.get("planCompliance") or [],
        "riskStats": (
            (context.get("riskStats") or [])[:6]
            if isinstance(context.get("riskStats"), list)
            else []
        ),
        "timeAnalytics": _slim_time_analytics(context.get("timeAnalytics") or {}),
        "psychology": {
            "preTradeEmotions": (
                _top_by_trade_count(psychology["preTradeEmotions"], 6)
                if isinstance(psychology.get("preTradeEmotions"), list)
                else []
            ),
            "postTradeEmotions": (
                _top_by_trade_count(psychology["postTradeEmotions"], 6)
                if isinstance(psychology.get("postTradeEmotions"), list)
                else []
            ),
            "confidence": (
                psychology["confidence"]
                if isinstance(psychology.get("confidence"), list)
                else []
            ),
            "marketBias": (
                psychology["marketBias"]
                if isinstance(psychology.get("marketBias"), list)
                else []
            ),
        },
        "direction": {
            "overall": (
                direction["overall"] if isinstance(direction.get("overall"), list) else []
            ),
            "byInstrument": (
                direction["byInstrument"][:TOP_N]
                if isinstance(direction.get("byInstrument"), list)
                else []
            ),
        },
        "behavior": {
            "afterLossesComparison": behavior.get("afterLossesComparison"),
            "earlyWinnerExit": behavior.get("earlyWinnerExit"),
        },
        "insights": _slim_insights(context.get("insights") or {}),
        "periodComparison": context.get("periodComparison") or {},
    }
