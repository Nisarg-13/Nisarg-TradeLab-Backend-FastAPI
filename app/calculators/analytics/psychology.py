from typing import Literal, TypedDict

from .trade_metrics import MetricTrade, group_trade_metrics

Direction = Literal["LONG", "SHORT"]


class PsychologyTrade(MetricTrade):
    pre_trade_emotion: str | None
    post_trade_emotion: str | None
    confidence_score: int | None
    market_bias: str | None
    direction: Direction


BIAS_ALIGNMENT_LABELS: dict[str, str] = {
    "aligned": "Aligned with bias",
    "against": "Against bias",
    "neutral": "Neutral / no bias",
}


def _format_emotion_label(value: str | None) -> str:
    if not value:
        return "Not recorded"

    return " ".join(part.capitalize() for part in value.lower().split("_"))


def _get_confidence_bucket(score: int) -> dict[str, str]:
    if score <= 3:
        return {"key": "low", "label": "Low (1–3)"}
    if score <= 6:
        return {"key": "medium", "label": "Medium (4–6)"}
    if score <= 8:
        return {"key": "high", "label": "High (7–8)"}
    return {"key": "very_high", "label": "Very high (9–10)"}


def _get_bias_alignment(market_bias: str | None, direction: Direction) -> str:
    if not market_bias or market_bias == "NEUTRAL":
        return "neutral"

    if (market_bias == "BULLISH" and direction == "LONG") or (
        market_bias == "BEARISH" and direction == "SHORT"
    ):
        return "aligned"

    return "against"


def summarize_psychology_analytics(trades: list[PsychologyTrade]) -> dict:
    pre_trade_emotions = group_trade_metrics(
        [trade for trade in trades if trade.get("pre_trade_emotion")],
        lambda trade: trade["pre_trade_emotion"],
        lambda key, _grouped: _format_emotion_label(key),
    )

    post_trade_emotions = group_trade_metrics(
        [trade for trade in trades if trade.get("post_trade_emotion")],
        lambda trade: trade["post_trade_emotion"],
        lambda key, _grouped: _format_emotion_label(key),
    )

    with_confidence = []
    for trade in trades:
        if trade.get("confidence_score") is None:
            continue
        bucket = _get_confidence_bucket(trade["confidence_score"])
        with_confidence.append(
            {
                **trade,
                "bucket_key": bucket["key"],
                "bucket_label": bucket["label"],
            }
        )

    confidence = group_trade_metrics(
        with_confidence,
        lambda trade: trade["bucket_key"],
        lambda key, grouped_trades: grouped_trades[0]["bucket_label"]
        if grouped_trades
        else key,
    )
    confidence.sort(key=lambda group: group["key"])

    with_bias = [trade for trade in trades if trade.get("market_bias")]

    market_bias = group_trade_metrics(
        with_bias,
        lambda trade: trade["market_bias"],
        lambda key, _grouped: _format_emotion_label(key),
    )

    with_alignment = [
        {
            **trade,
            "alignment_key": _get_bias_alignment(trade.get("market_bias"), trade["direction"]),
        }
        for trade in trades
    ]

    bias_alignment = group_trade_metrics(
        with_alignment,
        lambda trade: trade["alignment_key"],
        lambda key, _grouped: BIAS_ALIGNMENT_LABELS.get(key, key),
    )

    return {
        "pre_trade_emotions": pre_trade_emotions,
        "post_trade_emotions": post_trade_emotions,
        "confidence": confidence,
        "market_bias": market_bias,
        "bias_alignment": bias_alignment,
    }
