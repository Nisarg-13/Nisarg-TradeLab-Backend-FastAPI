from typing import Literal, TypedDict

from .sample_confidence import SampleConfidence
from .trade_metrics import summarize_trade_metrics

Direction = Literal["LONG", "SHORT"]


class DirectionTradeRecord(TypedDict):
    symbol: str
    direction: Direction
    net_pnl: float
    realized_r: float | None


class DirectionSideMetrics(TypedDict):
    direction: Direction
    label: str
    trade_count: int
    win_count: int
    loss_count: int
    net_pnl: float
    total_r: float | None
    win_rate: float | None
    average_r: float | None
    r_expectancy: float | None
    profit_factor: float | None
    sample_confidence: SampleConfidence


class InstrumentDirectionBreakdown(TypedDict):
    symbol: str
    long: DirectionSideMetrics | None
    short: DirectionSideMetrics | None


def _to_side_metrics(
    direction: Direction,
    trades: list[DirectionTradeRecord],
) -> DirectionSideMetrics | None:
    if not trades:
        return None

    metrics = summarize_trade_metrics(
        direction,
        "Long" if direction == "LONG" else "Short",
        trades,
    )

    return {
        "direction": direction,
        "label": metrics["label"],
        "trade_count": metrics["trade_count"],
        "win_count": metrics["win_count"],
        "loss_count": metrics["loss_count"],
        "net_pnl": metrics["net_pnl"],
        "total_r": metrics["total_r"],
        "win_rate": metrics["win_rate"],
        "average_r": metrics["average_r"],
        "r_expectancy": metrics["r_expectancy"],
        "profit_factor": metrics["profit_factor"],
        "sample_confidence": metrics["sample_confidence"],
    }


def summarize_overall_direction(
    trades: list[DirectionTradeRecord],
) -> list[DirectionSideMetrics]:
    long_trades = [trade for trade in trades if trade["direction"] == "LONG"]
    short_trades = [trade for trade in trades if trade["direction"] == "SHORT"]

    return [
        metrics
        for metrics in (
            _to_side_metrics("LONG", long_trades),
            _to_side_metrics("SHORT", short_trades),
        )
        if metrics is not None
    ]


def summarize_direction_by_instrument(
    trades: list[DirectionTradeRecord],
) -> list[InstrumentDirectionBreakdown]:
    symbols = sorted({trade["symbol"] for trade in trades})

    results = []
    for symbol in symbols:
        symbol_trades = [trade for trade in trades if trade["symbol"] == symbol]
        results.append(
            {
                "symbol": symbol,
                "long": _to_side_metrics(
                    "LONG",
                    [trade for trade in symbol_trades if trade["direction"] == "LONG"],
                ),
                "short": _to_side_metrics(
                    "SHORT",
                    [trade for trade in symbol_trades if trade["direction"] == "SHORT"],
                ),
            }
        )

    results.sort(
        key=lambda entry: (entry["long"]["net_pnl"] if entry["long"] else 0.0)
        + (entry["short"]["net_pnl"] if entry["short"] else 0.0),
        reverse=True,
    )

    return results
