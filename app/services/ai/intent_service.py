from __future__ import annotations

import re
from typing import Any, Literal

from app.schemas.ai import SampleConfidence, resolve_sample_confidence
from app.schemas.analytics import AnalyticsQuery, PeriodComparisonMode, PeriodComparisonQuery
from app.services.analytics import AnalyticsService

ChatIntent = Literal[
    "BEST_INSTRUMENT",
    "WORST_INSTRUMENT",
    "BEST_TIME",
    "WORST_TIME",
    "STRATEGY_PERFORMANCE",
    "RISK_PERFORMANCE",
    "PLAN_COMPLIANCE",
    "MISTAKE_COST",
    "PERIOD_COMPARISON",
    "AFTER_LOSSES",
    "EARLY_WINNER_EXIT",
    "GENERAL",
]


class AiIntentService:
    def __init__(self, analytics_service: AnalyticsService) -> None:
        self._analytics_service = analytics_service

    def classify_intent(self, question: str) -> ChatIntent:
        normalized = question.lower()

        if (
            re.search(r"best.*(instrument|symbol|pair|market)", normalized)
            or re.search(r"most profitable.*(instrument|symbol|pair|market)", normalized)
            or re.search(r"(instrument|symbol|pair|market).*most profitable", normalized)
        ):
            return "BEST_INSTRUMENT"

        if (
            re.search(r"worst.*(instrument|symbol|pair|market)", normalized)
            or re.search(r"least profitable.*(instrument|symbol|pair|market)", normalized)
        ):
            return "WORST_INSTRUMENT"

        if (
            re.search(r"best.*(time|hour|session|day)", normalized)
            or re.search(r"(time|hour|session|day).*perform best", normalized)
        ):
            return "BEST_TIME"

        if (
            re.search(r"worst.*(time|hour|session|day)", normalized)
            or re.search(r"lose the most.*(time|hour|session|day)", normalized)
            or re.search(r"(time|hour|session|day).*lose the most", normalized)
            or re.search(r"when do i lose the most", normalized)
        ):
            return "WORST_TIME"

        if re.search(r"strategy", normalized):
            return "STRATEGY_PERFORMANCE"

        if re.search(r"risk", normalized):
            return "RISK_PERFORMANCE"

        if re.search(r"plan|discipline|compliance", normalized):
            return "PLAN_COMPLIANCE"

        if re.search(r"mistake|error", normalized):
            return "MISTAKE_COST"

        if re.search(r"compare|recent|improv|getting better|getting worse", normalized):
            return "PERIOD_COMPARISON"

        if re.search(r"after.*(loss|losses|losing streak)", normalized):
            return "AFTER_LOSSES"

        if re.search(
            r"early.*(exit|winner|take profit|tp)|cut winners|leave money|"
            r"exit winners.*early|winners too early",
            normalized,
        ):
            return "EARLY_WINNER_EXIT"

        return "GENERAL"

    async def build_evidence(
        self,
        user_id: str,
        intent: ChatIntent,
        query: AnalyticsQuery,
    ) -> dict[str, Any]:
        if intent in ("BEST_INSTRUMENT", "WORST_INSTRUMENT"):
            instruments = await self._analytics_service.get_instrument_performance_for_user(
                user_id, query
            )
            sorted_instruments = sorted(
                instruments,
                key=lambda item: float(item.get("netPnl") or 0),
                reverse=True,
            )
            target = (
                sorted_instruments[0]
                if intent == "BEST_INSTRUMENT"
                else sorted_instruments[-1] if sorted_instruments else None
            )

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(target.get("tradeCount", 0) if target else 0),
                "summary": (
                    f"{target['symbol']}: {target['tradeCount']} trades, net PnL {target['netPnl']}, "
                    f"average R {target.get('averageR', 'n/a')}."
                    if target
                    else "No instrument performance data available yet."
                ),
                "points": [
                    f"{item['symbol']}: {item['tradeCount']} trades, net PnL {item['netPnl']}, "
                    f"win rate {item.get('winRate', 'n/a')}%"
                    for item in sorted_instruments[:5]
                ],
                "limitations": (
                    ["Instrument sample sizes may be too small for strong conclusions."]
                    if (target.get("tradeCount", 0) if target else 0) < 10
                    else []
                ),
                "payload": {"target": target, "instruments": sorted_instruments[:5]},
            }

        if intent in ("BEST_TIME", "WORST_TIME"):
            time_analytics = await self._analytics_service.get_time_analytics_for_user(
                user_id, query, "UTC"
            )
            hours = sorted(
                time_analytics.get("hours") or [],
                key=lambda item: float(item.get("netPnl") or 0),
                reverse=True,
            )
            target = hours[0] if intent == "BEST_TIME" else (hours[-1] if hours else None)

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(target.get("tradeCount", 0) if target else 0),
                "summary": (
                    f"Hour {target['label']}: {target['tradeCount']} trades, net PnL {target['netPnl']}."
                    if target
                    else "No time-of-day analytics available yet."
                ),
                "points": [
                    f"{item['label']}: {item['tradeCount']} trades, net PnL {item['netPnl']}"
                    for item in hours[:5]
                ],
                "limitations": ["Time buckets combine all instruments and strategies."],
                "payload": {"target": target, "hours": hours[:5]},
            }

        if intent == "STRATEGY_PERFORMANCE":
            strategies = await self._analytics_service.get_strategy_performance_for_user(
                user_id, query
            )

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(
                    sum(item.get("tradeCount", 0) for item in strategies)
                ),
                "summary": (
                    f"Top strategy: {strategies[0]['strategyName']} with net PnL {strategies[0]['netPnl']}."
                    if strategies
                    else "No tagged strategy performance yet."
                ),
                "points": [
                    f"{item['strategyName']}: {item['tradeCount']} trades, net PnL {item['netPnl']}, "
                    f"win rate {item.get('winRate', 'n/a')}%"
                    for item in strategies[:5]
                ],
                "limitations": ["Untagged trades are excluded from strategy analytics."],
                "payload": {"strategies": strategies[:5]},
            }

        if intent == "RISK_PERFORMANCE":
            summary, risk_stats = await self._gather(
                self._analytics_service.get_summary_for_user(user_id, query),
                self._analytics_service.get_risk_stats_for_user(user_id, query),
            )

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(summary.get("closedTradeCount", 0)),
                "summary": (
                    f"Average R {summary.get('averageR', 'n/a')}, max drawdown "
                    f"{summary.get('maxDrawdownPercentage', 'n/a')}%, current open risk "
                    f"{summary.get('currentOpenRisk', 'n/a')}."
                ),
                "points": [
                    f"{item['label']}: {item['tradeCount']} trades, win rate {item.get('winRate', 'n/a')}%"
                    for item in risk_stats[:5]
                ],
                "limitations": ["Risk stats depend on logged initial risk values."],
                "payload": {"summary": summary, "riskStats": risk_stats[:5]},
            }

        if intent == "PLAN_COMPLIANCE":
            plan_compliance = await self._analytics_service.get_plan_compliance_for_user(
                user_id, query
            )
            followed = next(
                (item for item in plan_compliance if item.get("planCompliance") == "FOLLOWED"),
                None,
            )

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(
                    sum(item.get("tradeCount", 0) for item in plan_compliance)
                ),
                "summary": (
                    f"Followed plan expectancy R {followed.get('rExpectancy', 'n/a') if followed else 'n/a'}."
                    if plan_compliance
                    else "No plan compliance reviews logged yet."
                ),
                "points": [
                    f"{item['label']}: {item['tradeCount']} trades, net PnL {item['netPnl']}, "
                    f"expectancy R {item.get('rExpectancy', 'n/a')}"
                    for item in plan_compliance
                ],
                "limitations": ["Requires trade reviews with plan compliance set."],
                "payload": {"planCompliance": plan_compliance},
            }

        if intent == "MISTAKE_COST":
            mistakes = await self._analytics_service.get_mistake_analytics_for_user(
                user_id, query
            )

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(
                    sum(item.get("tradeCount", 0) for item in mistakes)
                ),
                "summary": (
                    f"Most costly mistake: {mistakes[0]['mistakeName']} with net PnL {mistakes[0]['netPnl']}."
                    if mistakes
                    else "No mistake tags recorded yet."
                ),
                "points": [
                    f"{item['mistakeName']}: {item['tradeCount']} trades, net PnL {item['netPnl']}"
                    for item in mistakes[:5]
                ],
                "limitations": ["Mistake analytics require tagged trade reviews."],
                "payload": {"mistakes": mistakes[:5]},
            }

        if intent == "PERIOD_COMPARISON":
            comparison = await self._analytics_service.get_period_comparison_for_user(
                user_id,
                PeriodComparisonQuery(
                    **query.model_dump(exclude_unset=True),
                    mode=PeriodComparisonMode.LATEST_20_VS_PREVIOUS_20,
                ),
            )

            period_a = comparison["periodA"]
            period_b = comparison["periodB"]

            return {
                "intent": intent,
                "sampleConfidence": period_a.get("sampleConfidence"),
                "summary": (
                    f"Latest window net PnL {period_a.get('netPnl')} vs previous {period_b.get('netPnl')}."
                ),
                "points": [
                    f"{period_a.get('label')}: {period_a.get('tradeCount')} trades, "
                    f"win rate {period_a.get('winRate', 'n/a')}%",
                    f"{period_b.get('label')}: {period_b.get('tradeCount')} trades, "
                    f"win rate {period_b.get('winRate', 'n/a')}%",
                ],
                "limitations": ["Comparison uses the latest closed-trade windows only."],
                "payload": {"comparison": comparison},
            }

        if intent == "AFTER_LOSSES":
            after_losses = await self._analytics_service.get_after_losses_analytics_for_user(
                user_id, query, 2
            )

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(after_losses.get("tradeCount", 0)),
                "summary": (
                    f"After 2 losses: {after_losses['tradeCount']} trades, net PnL {after_losses['netPnl']}, "
                    f"win rate {after_losses.get('winRate', 'n/a')}%. Baseline win rate "
                    f"{after_losses.get('baselineWinRate', 'n/a')}%."
                    if after_losses.get("tradeCount", 0) > 0
                    else "Not enough closed trades following loss streaks yet."
                ),
                "points": [
                    f"After-loss trades: {after_losses.get('tradeCount')}",
                    f"After-loss net PnL: {after_losses.get('netPnl')}",
                    f"Baseline net PnL: {after_losses.get('baselineNetPnl')}",
                ],
                "limitations": (
                    ["Few trades occurred immediately after 2 consecutive losses."]
                    if after_losses.get("tradeCount", 0) < 10
                    else ["Association only — streak context does not prove causation."]
                ),
                "payload": {"afterLosses": after_losses},
            }

        if intent == "EARLY_WINNER_EXIT":
            early_exits = await self._analytics_service.get_early_winner_exit_analytics_for_user(
                user_id, query
            )

            return {
                "intent": intent,
                "sampleConfidence": resolve_sample_confidence(early_exits.get("winnerCount", 0)),
                "summary": (
                    f"{early_exits.get('earlyExitCount')} of {early_exits.get('winnerCount')} winners "
                    f"captured less than 75% of planned R. Average planned R "
                    f"{early_exits.get('averagePlannedR', 'n/a')}, average realized R "
                    f"{early_exits.get('averageRealizedR', 'n/a')}."
                    if early_exits.get("winnerCount", 0) > 0
                    else "No closed winners with both planned and realized R logged yet."
                ),
                "points": [
                    f"Early exit rate: {early_exits.get('earlyExitRate', 'n/a')}%",
                    f"Average capture ratio: {early_exits.get('averageCaptureRatio', 'n/a')}%",
                ],
                "limitations": [
                    "Requires both planned R:R and realized R on winning trades.",
                ],
                "payload": {"earlyExits": early_exits},
            }

        summary = await self._analytics_service.get_summary_for_user(user_id, query)

        return {
            "intent": "GENERAL",
            "sampleConfidence": summary.get("sampleConfidence"),
            "summary": (
                f"{summary.get('closedTradeCount')} closed trades, net PnL {summary.get('netPnl')}, "
                f"win rate {summary.get('winRate', 'n/a')}%, profit factor {summary.get('profitFactor', 'n/a')}."
            ),
            "points": [
                f"Expectancy R: {summary.get('rExpectancy', 'n/a')}",
                f"Average winner: {summary.get('averageWinner', 'n/a')}",
                f"Average loser: {summary.get('averageLoser', 'n/a')}",
            ],
            "limitations": (
                ["Sample size is still limited for broad coaching questions."]
                if summary.get("closedTradeCount", 0) < 20
                else []
            ),
            "payload": {"summary": summary},
        }

    @staticmethod
    async def _gather(*awaitables: Any) -> tuple[Any, ...]:
        import asyncio

        return tuple(await asyncio.gather(*awaitables))
