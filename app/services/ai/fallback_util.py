from __future__ import annotations

from typing import Any

from app.schemas.ai import AiChatAnswer, AiStructuredOutput, SampleConfidence
from app.services.ai.coaching_util import build_data_driven_analysis


def build_fallback_analysis(
    context: dict[str, Any],
    provider_label: str,
    fallback_reason: str | None = None,
) -> AiStructuredOutput:
    output = build_data_driven_analysis(context, provider_label=provider_label)

    if fallback_reason:
        filtered = [
            item
            for item in output.data_limitations
            if "unavailable" not in item.lower()
        ]

        return AiStructuredOutput(
            summary=output.summary,
            strengths=output.strengths,
            weaknesses=output.weaknesses,
            patterns=output.patterns,
            recommendations=output.recommendations,
            rules_for_next_trades=output.rules_for_next_trades,
            data_limitations=[*filtered, f"AI narrative unavailable: {fallback_reason}"][:6],
        )

    return output


def build_fallback_chat_answer(
    intent: str,
    evidence: dict[str, Any],
    provider_label: str,
) -> AiChatAnswer:
    confidence: SampleConfidence = evidence.get("sampleConfidence") or "INSUFFICIENT"

    summary_text = (
        evidence["summary"]
        if isinstance(evidence.get("summary"), str)
        else "Here is what your journal data shows."
    )

    points = evidence.get("points")
    limitations = evidence.get("limitations")

    return AiChatAnswer(
        intent=intent,
        confidence=confidence,
        summary=summary_text,
        evidence=[str(item) for item in points] if isinstance(points, list) else [],
        limitations=(
            [str(item) for item in limitations]
            if isinstance(limitations, list)
            else [f"Generated without {provider_label} — based on calculated analytics only."]
        ),
    )
