from dataclasses import dataclass
from typing import Callable, Literal, TypedDict

from .expectancy import calculate_average_r, calculate_r_expectancy, calculate_total_r
from .pnl import calculate_net_pnl, calculate_profit_factor
from .sample_confidence import SampleConfidence, get_sample_confidence
from .win_rate import calculate_win_rate

EDGE_FINDER_MIN_SAMPLE = 10
EDGE_FINDER_MAX_RESULTS = 15

Direction = Literal["LONG", "SHORT"]


class EdgeFinderTrade(TypedDict):
    symbol: str
    direction: Direction
    strategy_names: list[str]
    session: str
    tag_names: list[str]
    risk_bucket: str
    plan_compliance: str
    net_pnl: float
    realized_r: float | None


class EdgeFinderDimension(TypedDict):
    key: str
    label: str
    value: str


class EdgeFinderCombination(TypedDict):
    dimensions: list[EdgeFinderDimension]
    trade_count: int
    net_pnl: float
    total_r: float | None
    win_rate: float | None
    average_r: float | None
    r_expectancy: float | None
    profit_factor: float | None
    sample_confidence: SampleConfidence
    score: float


class EdgeFinderInput(TypedDict, total=False):
    symbol: str
    direction: Direction
    strategy_names: list[str]
    session: str
    tag_names: list[str]
    initial_risk_percentage: float | None
    plan_compliance: str | None
    net_pnl: float
    realized_r: float | None


class EdgeFinderResult(TypedDict):
    minimum_sample_size: int
    strongest: list[EdgeFinderCombination]
    weakest: list[EdgeFinderCombination]
    evaluated_combination_count: int


@dataclass(frozen=True)
class DimensionDef:
    key: str
    label: str
    get_values: Callable[[EdgeFinderTrade], list[str]]


def _get_risk_bucket(risk_percentage: float | None) -> str:
    if risk_percentage is None:
        return "Unknown risk"

    if risk_percentage <= 0.5:
        return "≤ 0.50%"

    if risk_percentage <= 1:
        return "0.51% – 1.00%"

    if risk_percentage <= 2:
        return "1.01% – 2.00%"

    return "> 2.00%"


def _format_plan_compliance(value: str | None) -> str:
    if not value or value == "NOT_REVIEWED":
        return "Not reviewed"

    return " ".join(part.capitalize() for part in value.lower().split("_"))


def to_edge_finder_trade(trade: EdgeFinderInput) -> EdgeFinderTrade:
    return {
        "symbol": trade["symbol"],
        "direction": trade["direction"],
        "strategy_names": trade.get("strategy_names", []),
        "session": trade["session"],
        "tag_names": trade.get("tag_names", []),
        "risk_bucket": _get_risk_bucket(trade.get("initial_risk_percentage")),
        "plan_compliance": _format_plan_compliance(trade.get("plan_compliance")),
        "net_pnl": trade["net_pnl"],
        "realized_r": trade.get("realized_r"),
    }


DIMENSIONS: list[DimensionDef] = [
    DimensionDef("symbol", "Instrument", lambda trade: [trade["symbol"]]),
    DimensionDef("direction", "Direction", lambda trade: [trade["direction"]]),
    DimensionDef(
        "strategy",
        "Strategy",
        lambda trade: trade["strategy_names"] if trade["strategy_names"] else ["No strategy"],
    ),
    DimensionDef("session", "Session", lambda trade: [trade["session"]]),
    DimensionDef(
        "tag",
        "Entry criteria",
        lambda trade: trade["tag_names"] if trade["tag_names"] else ["No entry criteria"],
    ),
    DimensionDef("risk", "Risk bucket", lambda trade: [trade["risk_bucket"]]),
    DimensionDef(
        "planCompliance",
        "Plan compliance",
        lambda trade: [trade["plan_compliance"]],
    ),
]


def _summarize_combination(
    dimensions: list[EdgeFinderDimension],
    trades: list[EdgeFinderTrade],
) -> EdgeFinderCombination:
    metric_trades = [
        {"net_pnl": trade["net_pnl"], "realized_r": trade["realized_r"]} for trade in trades
    ]
    average_r = calculate_average_r(metric_trades)
    r_expectancy = calculate_r_expectancy(metric_trades)

    return {
        "dimensions": dimensions,
        "trade_count": len(trades),
        "net_pnl": calculate_net_pnl(metric_trades),
        "total_r": calculate_total_r(metric_trades),
        "win_rate": calculate_win_rate(metric_trades),
        "average_r": average_r,
        "r_expectancy": r_expectancy,
        "profit_factor": calculate_profit_factor(metric_trades),
        "sample_confidence": get_sample_confidence(len(trades)),
        "score": r_expectancy if r_expectancy is not None else (average_r or 0.0),
    }


def _build_combinations(
    trades: list[EdgeFinderTrade],
    size: int,
) -> list[EdgeFinderCombination]:
    results: list[EdgeFinderCombination] = []
    dimension_count = len(DIMENSIONS)

    def choose(start: int, picked: list[DimensionDef]) -> None:
        if len(picked) == size:
            groups: dict[str, dict] = {}

            for trade in trades:
                value_lists = [dimension.get_values(trade) for dimension in picked]
                combos: list[list[str]] = [[]]
                for values in value_lists:
                    combos = [prefix + [value] for prefix in combos for value in values]

                for combo in combos:
                    values = [
                        {
                            "key": picked[index].key,
                            "label": picked[index].label,
                            "value": combo[index],
                        }
                        for index in range(len(picked))
                    ]
                    group_key = "|".join(f"{entry['key']}:{entry['value']}" for entry in values)
                    current = groups.get(group_key, {"dimensions": values, "trades": []})
                    current["trades"].append(trade)
                    groups[group_key] = current

            for group in groups.values():
                if len(group["trades"]) < EDGE_FINDER_MIN_SAMPLE:
                    continue

                results.append(_summarize_combination(group["dimensions"], group["trades"]))

            return

        for index in range(start, dimension_count - (size - len(picked)) + 1):
            choose(index + 1, picked + [DIMENSIONS[index]])

    choose(0, [])
    return results


def discover_edge_combinations(trades: list[EdgeFinderTrade]) -> EdgeFinderResult:
    combinations = [
        combination
        for size in (2, 3, 4)
        for combination in _build_combinations(trades, size)
    ]

    unique: dict[str, EdgeFinderCombination] = {}

    for combination in combinations:
        key = "|".join(
            f"{dimension['key']}:{dimension['value']}" for dimension in combination["dimensions"]
        )
        existing = unique.get(key)

        if existing is None or existing["trade_count"] < combination["trade_count"]:
            unique[key] = combination

    ranked = sorted(
        unique.values(),
        key=lambda item: (item["score"], item["trade_count"]),
        reverse=True,
    )

    strongest = ranked[:EDGE_FINDER_MAX_RESULTS]
    weakest = sorted(
        unique.values(),
        key=lambda item: (item["score"], -item["trade_count"]),
    )[:EDGE_FINDER_MAX_RESULTS]

    return {
        "minimum_sample_size": EDGE_FINDER_MIN_SAMPLE,
        "strongest": strongest,
        "weakest": weakest,
        "evaluated_combination_count": len(unique),
    }
