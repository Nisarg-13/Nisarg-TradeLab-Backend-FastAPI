from typing import Literal

SampleConfidence = Literal[
    "INSUFFICIENT",
    "VERY_LOW",
    "LOW",
    "MODERATE",
    "HIGHER",
]


def get_sample_confidence(trade_count: int) -> SampleConfidence:
    if trade_count < 5:
        return "INSUFFICIENT"
    if trade_count < 10:
        return "VERY_LOW"
    if trade_count < 20:
        return "LOW"
    if trade_count < 50:
        return "MODERATE"
    return "HIGHER"
