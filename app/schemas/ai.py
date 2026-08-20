from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SampleConfidence = Literal["HIGH", "MODERATE", "LOW", "INSUFFICIENT"]


def resolve_sample_confidence(sample_size: int) -> SampleConfidence:
    if sample_size >= 50:
        return "HIGH"
    if sample_size >= 20:
        return "MODERATE"
    if sample_size >= 5:
        return "LOW"
    return "INSUFFICIENT"


class AiAnalysisQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trading_account_id: str | None = Field(default=None, min_length=1, alias="tradingAccountId")


class AiChatInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(min_length=3, max_length=2000)
    trading_account_id: str | None = Field(default=None, min_length=1, alias="tradingAccountId")


class AiStructuredOutput(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    patterns: list[str]
    recommendations: list[str]
    rules_for_next_trades: list[str] = Field(alias="rulesForNextTrades")
    data_limitations: list[str] = Field(alias="dataLimitations")

    model_config = ConfigDict(populate_by_name=True)


class AiChatAnswer(BaseModel):
    intent: str
    confidence: SampleConfidence
    summary: str
    evidence: list[str]
    limitations: list[str]
