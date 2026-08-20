from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.schemas.ai import SampleConfidence, resolve_sample_confidence
from app.schemas.analytics import AnalyticsQuery, PeriodComparisonMode, PeriodComparisonQuery
from app.services.analytics import AnalyticsService


class AiContextPayload(TypedDict):
    sampleSize: int
    sampleConfidence: SampleConfidence
    timezone: str
    summary: dict[str, Any]
    instruments: list[dict[str, Any]]
    strategies: list[dict[str, Any]]
    tags: list[dict[str, Any]]
    planCompliance: list[dict[str, Any]]
    riskStats: list[dict[str, Any]]
    timeAnalytics: dict[str, Any]
    psychology: dict[str, Any]
    mistakes: list[dict[str, Any]]
    direction: dict[str, Any]
    behavior: dict[str, Any]
    insights: dict[str, Any]
    periodComparison: dict[str, Any]


class AiContextBuilder:
    def __init__(
        self,
        db: AsyncSession,
        analytics_service: AnalyticsService,
    ) -> None:
        self._db = db
        self._analytics_service = analytics_service

    async def build_for_user(
        self,
        user_id: str,
        query: AnalyticsQuery,
    ) -> AiContextPayload:
        result = await self._db.execute(select(User.timezone).where(User.id == user_id))
        timezone = result.scalar_one_or_none() or "UTC"

        comparison_query = PeriodComparisonQuery(
            **query.model_dump(exclude_unset=True),
            mode=PeriodComparisonMode.LATEST_20_VS_PREVIOUS_20,
        )

        (
            summary,
            instruments,
            strategies,
            tags,
            plan_compliance,
            risk_stats,
            time_analytics,
            psychology,
            mistakes,
            direction,
            behavior,
            insights,
            period_comparison,
        ) = await asyncio.gather(
            self._analytics_service.get_summary_for_user(user_id, query),
            self._analytics_service.get_instrument_performance_for_user(user_id, query),
            self._analytics_service.get_strategy_performance_for_user(user_id, query),
            self._analytics_service.get_tag_analytics_for_user(user_id, query),
            self._analytics_service.get_plan_compliance_for_user(user_id, query),
            self._analytics_service.get_risk_stats_for_user(user_id, query),
            self._analytics_service.get_time_analytics_for_user(user_id, query, timezone),
            self._analytics_service.get_psychology_analytics_for_user(user_id, query),
            self._analytics_service.get_mistake_analytics_for_user(user_id, query),
            self._analytics_service.get_direction_analytics_for_user(user_id, query),
            self._analytics_service.get_behavior_analytics_for_user(user_id, query),
            self._analytics_service.get_insights_for_user(user_id, query, timezone),
            self._analytics_service.get_period_comparison_for_user(user_id, comparison_query),
        )

        sample_size = summary.get("closedTradeCount", 0)

        return {
            "sampleSize": sample_size,
            "sampleConfidence": resolve_sample_confidence(sample_size),
            "timezone": timezone,
            "summary": summary,
            "instruments": instruments,
            "strategies": strategies,
            "tags": tags,
            "planCompliance": plan_compliance,
            "riskStats": risk_stats,
            "timeAnalytics": time_analytics,
            "psychology": psychology,
            "mistakes": mistakes,
            "direction": direction,
            "behavior": behavior,
            "insights": insights,
            "periodComparison": period_comparison,
        }
