from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas.ai import AiChatAnswer, AiStructuredOutput
from app.services.ai.context_serializer import slim_context_for_llm
from app.services.ai.fallback_util import build_fallback_analysis, build_fallback_chat_answer
from app.services.ai.output_normalizer import normalize_chat_answer, normalize_structured_output
from app.services.ai.prompts import AI_COACH_SYSTEM_PROMPT, build_analysis_prompt

logger = logging.getLogger(__name__)

AiGenerationSource = Literal["openai", "gemini", "analytics"]


@dataclass
class AiAnalysisGeneration:
    output: AiStructuredOutput
    source: AiGenerationSource
    fallback_reason: str | None = None


@dataclass
class AiChatGeneration:
    output: AiChatAnswer
    source: AiGenerationSource
    fallback_reason: str | None = None


def _build_chat_prompt(question: str, intent: str, evidence: dict[str, Any]) -> str:
    return f"""Answer the trader's journal question using only the supplied evidence.
Return JSON with keys: intent, confidence, summary, evidence, limitations.
intent must be "{intent}".
confidence must be one of HIGH, MODERATE, LOW, INSUFFICIENT.
evidence and limitations must be string arrays.

Question: {question}

Evidence:
{json.dumps(evidence, indent=2)}"""


class OpenAiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _get_api_key(self) -> str:
        return (self._settings.OPENAI_API_KEY or "").strip()

    def is_configured(self) -> bool:
        return len(self._get_api_key()) > 0

    def get_model(self) -> str:
        return self._settings.OPENAI_MODEL or "gpt-4o-mini"

    async def generate_analysis(self, context: dict[str, Any]) -> AiAnalysisGeneration:
        if not self.is_configured():
            return AiAnalysisGeneration(
                output=build_fallback_analysis(context, "OpenAI"),
                source="analytics",
                fallback_reason="OPENAI_API_KEY is not set on the server.",
            )

        slim_context = slim_context_for_llm(context)

        try:
            prompt = build_analysis_prompt(slim_context)
            raw = await self._generate_json(prompt)
            normalized = normalize_structured_output(raw)

            try:
                parsed = AiStructuredOutput.model_validate(normalized)
            except ValidationError as error:
                logger.warning("OpenAI analysis JSON failed schema validation: %s", error)
                return AiAnalysisGeneration(
                    output=build_fallback_analysis(
                        context,
                        "OpenAI",
                        "OpenAI returned an invalid response format.",
                    ),
                    source="analytics",
                    fallback_reason="OpenAI returned an invalid response format.",
                )

            return AiAnalysisGeneration(output=parsed, source="openai")
        except Exception as error:
            message = str(error) if str(error) else "unknown OpenAI error"
            logger.warning("Falling back from OpenAI analysis: %s", message)
            return AiAnalysisGeneration(
                output=build_fallback_analysis(context, "OpenAI", message),
                source="analytics",
                fallback_reason=message,
            )

    async def generate_chat_answer(
        self,
        question: str,
        intent: str,
        evidence: dict[str, Any],
    ) -> AiChatGeneration:
        if not self.is_configured():
            return AiChatGeneration(
                output=build_fallback_chat_answer(intent, evidence, "OpenAI"),
                source="analytics",
                fallback_reason="OPENAI_API_KEY is not set on the server.",
            )

        try:
            prompt = _build_chat_prompt(question, intent, evidence)
            raw = await self._generate_json(prompt)
            normalized = normalize_chat_answer(raw)

            try:
                parsed = AiChatAnswer.model_validate(normalized)
            except ValidationError as error:
                logger.warning("OpenAI chat JSON failed schema validation: %s", error)
            else:
                return AiChatGeneration(output=parsed, source="openai")
        except Exception as error:
            logger.warning(
                "Falling back from OpenAI chat: %s",
                str(error) if str(error) else "unknown error",
            )

        return AiChatGeneration(
            output=build_fallback_chat_answer(intent, evidence, "OpenAI"),
            source="analytics",
            fallback_reason="OpenAI chat request failed.",
        )

    async def _generate_json(self, prompt: str) -> Any:
        api_key = self._get_api_key()

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json={
                    "model": self.get_model(),
                    "messages": [
                        {"role": "system", "content": AI_COACH_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 4096,
                },
            )

        if not response.is_success:
            logger.warning("OpenAI request failed: %s %s", response.status_code, response.text)
            raise RuntimeError(f"OpenAI request failed ({response.status_code})")

        payload = response.json()
        choice = (payload.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content")

        if not text:
            raise RuntimeError("OpenAI returned an empty response")

        if choice.get("finish_reason") == "length":
            logger.warning("OpenAI response was truncated due to token limit")

        return json.loads(text)


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool((self._settings.GEMINI_API_KEY or "").strip())

    async def generate_analysis(self, context: dict[str, Any]) -> AiAnalysisGeneration:
        if not self.is_configured():
            return AiAnalysisGeneration(
                output=build_fallback_analysis(context, "Gemini"),
                source="analytics",
                fallback_reason="GEMINI_API_KEY is not set on the server.",
            )

        slim_context = slim_context_for_llm(context)

        try:
            prompt = build_analysis_prompt(slim_context)
            raw = await self._generate_json(prompt)
            normalized = normalize_structured_output(raw)

            try:
                parsed = AiStructuredOutput.model_validate(normalized)
            except ValidationError as error:
                logger.warning("Gemini analysis JSON failed schema validation: %s", error)
            else:
                return AiAnalysisGeneration(output=parsed, source="gemini")
        except Exception as error:
            logger.warning(
                "Falling back from Gemini analysis: %s",
                str(error) if str(error) else "unknown error",
            )

        return AiAnalysisGeneration(
            output=build_fallback_analysis(context, "Gemini"),
            source="analytics",
            fallback_reason="Gemini request failed or returned invalid JSON.",
        )

    async def generate_chat_answer(
        self,
        question: str,
        intent: str,
        evidence: dict[str, Any],
    ) -> AiChatGeneration:
        if not self.is_configured():
            return AiChatGeneration(
                output=build_fallback_chat_answer(intent, evidence, "Gemini"),
                source="analytics",
                fallback_reason="GEMINI_API_KEY is not set on the server.",
            )

        try:
            prompt = _build_chat_prompt(question, intent, evidence)
            raw = await self._generate_json(prompt)
            normalized = normalize_chat_answer(raw)

            try:
                parsed = AiChatAnswer.model_validate(normalized)
            except ValidationError:
                pass
            else:
                return AiChatGeneration(output=parsed, source="gemini")
        except Exception as error:
            logger.warning(
                "Falling back from Gemini chat: %s",
                str(error) if str(error) else "unknown error",
            )

        return AiChatGeneration(
            output=build_fallback_chat_answer(intent, evidence, "Gemini"),
            source="analytics",
            fallback_reason="Gemini chat request failed.",
        )

    async def _generate_json(self, prompt: str) -> Any:
        api_key = (self._settings.GEMINI_API_KEY or "").strip()

        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": AI_COACH_SYSTEM_PROMPT}]},
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.2,
                    },
                },
            )

        if not response.is_success:
            logger.warning("Gemini request failed: %s %s", response.status_code, response.text)
            raise RuntimeError(f"Gemini request failed ({response.status_code})")

        payload = response.json()
        candidates = payload.get("candidates") or [{}]
        parts = ((candidates[0].get("content") or {}).get("parts") or [{}])
        text = parts[0].get("text")

        if not text:
            raise RuntimeError("Gemini returned an empty response")

        return json.loads(text)


class AiLlmClient:
    def __init__(self, settings: Settings) -> None:
        self._openai_client = OpenAiClient(settings)
        self._gemini_client = GeminiClient(settings)

    def is_configured(self) -> bool:
        return self._openai_client.is_configured() or self._gemini_client.is_configured()

    def get_status(self) -> dict[str, Any]:
        return {
            "openaiConfigured": self._openai_client.is_configured(),
            "openaiModel": (
                self._openai_client.get_model()
                if self._openai_client.is_configured()
                else None
            ),
            "geminiConfigured": self._gemini_client.is_configured(),
        }

    async def generate_analysis(self, context: dict[str, Any]) -> AiAnalysisGeneration:
        if self._openai_client.is_configured():
            return await self._openai_client.generate_analysis(context)

        return await self._gemini_client.generate_analysis(context)

    async def generate_chat_answer(
        self,
        question: str,
        intent: str,
        evidence: dict[str, Any],
    ) -> AiChatGeneration:
        if self._openai_client.is_configured():
            return await self._openai_client.generate_chat_answer(question, intent, evidence)

        return await self._gemini_client.generate_chat_answer(question, intent, evidence)
