from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies.database import DbSession
from app.models.models import AiAnalysis, AiChatMessage
from app.schemas.ai import AiAnalysisQuery, AiChatInput
from app.schemas.analytics import AnalyticsQuery
from app.services.ai.context_builder import AiContextBuilder
from app.services.ai.intent_service import AiIntentService
from app.services.ai.llm_clients import AiLlmClient
from app.services.analytics import AnalyticsService, get_analytics_service
from app.utils.ids import generate_cuid


class AiService:
    def __init__(
        self,
        db: AsyncSession,
        context_builder: AiContextBuilder,
        intent_service: AiIntentService,
        llm_client: AiLlmClient,
    ) -> None:
        self._db = db
        self._context_builder = context_builder
        self._intent_service = intent_service
        self._llm_client = llm_client

    async def generate_analysis_for_user(
        self,
        user_id: str,
        query: AiAnalysisQuery,
    ) -> dict[str, Any]:
        analytics_query = AnalyticsQuery(trading_account_id=query.trading_account_id)
        context = await self._context_builder.build_for_user(user_id, analytics_query)
        generation = await self._llm_client.generate_analysis(context)

        saved = AiAnalysis(
            id=generate_cuid(),
            user_id=user_id,
            trading_account_id=query.trading_account_id,
            sample_size=context["sampleSize"],
            sample_confidence=context["sampleConfidence"],
            summary=generation.output.summary,
            strengths=generation.output.strengths,
            weaknesses=generation.output.weaknesses,
            patterns=generation.output.patterns,
            recommendations=generation.output.recommendations,
            rules_for_next_trades=generation.output.rules_for_next_trades,
            data_limitations=generation.output.data_limitations,
            context={
                **context,
                "_meta": {
                    "source": generation.source,
                    "fallbackReason": generation.fallback_reason,
                },
            },
        )

        self._db.add(saved)
        await self._db.commit()
        await self._db.refresh(saved)

        return self._to_analysis_response(saved)

    async def list_analyses_for_user(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        result = await self._db.execute(
            select(AiAnalysis)
            .where(AiAnalysis.user_id == user_id)
            .order_by(AiAnalysis.created_at.desc())
            .limit(limit)
        )
        analyses = list(result.scalars().all())
        return [self._to_analysis_response(analysis) for analysis in analyses]

    async def get_analysis_for_user(
        self,
        user_id: str,
        analysis_id: str,
    ) -> dict[str, Any] | None:
        result = await self._db.execute(
            select(AiAnalysis).where(AiAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()

        if not analysis or analysis.user_id != user_id:
            return None

        return self._to_analysis_response(analysis)

    def get_provider_status(self) -> dict[str, Any]:
        return self._llm_client.get_status()

    async def ask_journal_for_user(
        self,
        user_id: str,
        input_data: AiChatInput,
    ) -> dict[str, Any]:
        analytics_query = AnalyticsQuery(trading_account_id=input_data.trading_account_id)

        intent = self._intent_service.classify_intent(input_data.question)
        evidence = await self._intent_service.build_evidence(user_id, intent, analytics_query)

        generation = await self._llm_client.generate_chat_answer(
            input_data.question,
            intent,
            evidence,
        )

        saved = AiChatMessage(
            id=generate_cuid(),
            user_id=user_id,
            question=input_data.question,
            answer={
                **generation.output.model_dump(by_alias=True),
                "_meta": {
                    "source": generation.source,
                    "fallbackReason": generation.fallback_reason,
                },
            },
        )

        self._db.add(saved)
        await self._db.commit()
        await self._db.refresh(saved)

        return {
            "id": saved.id,
            "question": saved.question,
            "answer": generation.output.model_dump(by_alias=True),
            "createdAt": saved.created_at.isoformat(),
        }

    async def list_chat_history_for_user(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        result = await self._db.execute(
            select(AiChatMessage)
            .where(AiChatMessage.user_id == user_id)
            .order_by(AiChatMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())

        return [
            {
                "id": message.id,
                "question": message.question,
                "answer": message.answer,
                "createdAt": message.created_at.isoformat(),
            }
            for message in messages
        ]

    @staticmethod
    def _to_analysis_response(analysis: AiAnalysis) -> dict[str, Any]:
        context = analysis.context if isinstance(analysis.context, dict) else {}
        meta = context.get("_meta") if isinstance(context.get("_meta"), dict) else {}

        return {
            "id": analysis.id,
            "tradingAccountId": analysis.trading_account_id,
            "sampleSize": analysis.sample_size,
            "sampleConfidence": analysis.sample_confidence,
            "summary": analysis.summary,
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
            "patterns": analysis.patterns,
            "recommendations": analysis.recommendations,
            "rulesForNextTrades": analysis.rules_for_next_trades,
            "dataLimitations": analysis.data_limitations,
            "source": meta.get("source", "analytics"),
            "fallbackReason": meta.get("fallbackReason"),
            "createdAt": analysis.created_at.isoformat(),
        }


def get_ai_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AiLlmClient:
    return AiLlmClient(settings)


def get_ai_context_builder(
    db: DbSession,
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> AiContextBuilder:
    return AiContextBuilder(db, analytics_service)


def get_ai_intent_service(
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> AiIntentService:
    return AiIntentService(analytics_service)


def get_ai_service(
    db: DbSession,
    context_builder: Annotated[AiContextBuilder, Depends(get_ai_context_builder)],
    intent_service: Annotated[AiIntentService, Depends(get_ai_intent_service)],
    llm_client: Annotated[AiLlmClient, Depends(get_ai_llm_client)],
) -> AiService:
    return AiService(db, context_builder, intent_service, llm_client)


AiServiceDep = Annotated[AiService, Depends(get_ai_service)]
