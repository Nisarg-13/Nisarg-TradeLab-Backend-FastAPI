from datetime import datetime
from typing import Literal, TypedDict

from .costs import (
    calculate_total_commission,
    calculate_total_fees,
    calculate_total_swap,
    calculate_total_trading_costs,
)
from .expectancy import (
    calculate_average_r,
    calculate_money_expectancy,
    calculate_r_expectancy,
    calculate_total_r,
)
from .holding_time import (
    calculate_average_holding_time_minutes,
    calculate_median_holding_time_minutes,
)
from .pnl import (
    calculate_average_loser,
    calculate_average_win_loss_ratio,
    calculate_average_winner,
    calculate_gross_loss,
    calculate_gross_profit,
    calculate_largest_loser,
    calculate_largest_winner,
    calculate_net_pnl,
    calculate_profit_factor,
)
from .sample_confidence import SampleConfidence, get_sample_confidence
from .win_rate import (
    calculate_breakeven_rate,
    calculate_loss_rate,
    calculate_win_rate,
    count_breakeven,
    count_losses,
    count_wins,
)


class StrategyRef(TypedDict):
    id: str
    name: str


Direction = Literal["LONG", "SHORT"]


class AnalyticsTradeRecord(TypedDict, total=False):
    symbol: str
    strategies: list[StrategyRef]
    direction: Direction
    net_pnl: float
    realized_r: float | None


class ClosedTradeSummaryInput(AnalyticsTradeRecord, total=False):
    commission: float
    swap: float
    fees: float
    opened_at: datetime
    closed_at: datetime | None


class GroupedPerformance(TypedDict):
    key: str
    label: str
    trade_count: int
    net_pnl: float
    gross_profit: float
    gross_loss: float
    total_r: float | None
    win_rate: float | None
    average_r: float | None
    r_expectancy: float | None
    money_expectancy: float | None
    profit_factor: float | None
    long_trade_count: int
    short_trade_count: int
    long_net_pnl: float
    short_net_pnl: float
    sample_confidence: SampleConfidence


class ClosedTradeSummary(TypedDict):
    net_pnl: float
    gross_profit: float
    gross_loss: float
    win_count: int
    loss_count: int
    breakeven_count: int
    win_rate: float | None
    loss_rate: float | None
    breakeven_rate: float | None
    profit_factor: float | None
    money_expectancy: float | None
    r_expectancy: float | None
    average_r: float | None
    total_r: float | None
    average_winner: float | None
    average_loser: float | None
    average_win_loss_ratio: float | None
    largest_winner: float | None
    largest_loser: float | None
    average_holding_time_minutes: float | None
    median_holding_time_minutes: float | None
    total_commission: float
    total_swap: float
    total_fees: float
    total_trading_costs: float
    sample_confidence: SampleConfidence


def _summarize_trades(
    key: str,
    label: str,
    trades: list[AnalyticsTradeRecord],
) -> GroupedPerformance:
    long_trades = [trade for trade in trades if trade.get("direction") == "LONG"]
    short_trades = [trade for trade in trades if trade.get("direction") == "SHORT"]

    return {
        "key": key,
        "label": label,
        "trade_count": len(trades),
        "net_pnl": calculate_net_pnl(trades),
        "gross_profit": calculate_gross_profit(trades),
        "gross_loss": calculate_gross_loss(trades),
        "total_r": calculate_total_r(trades),
        "win_rate": calculate_win_rate(trades),
        "average_r": calculate_average_r(trades),
        "r_expectancy": calculate_r_expectancy(trades),
        "money_expectancy": calculate_money_expectancy(trades),
        "profit_factor": calculate_profit_factor(trades),
        "long_trade_count": len(long_trades),
        "short_trade_count": len(short_trades),
        "long_net_pnl": calculate_net_pnl(long_trades),
        "short_net_pnl": calculate_net_pnl(short_trades),
        "sample_confidence": get_sample_confidence(len(trades)),
    }


def summarize_by_instrument(
    trades: list[AnalyticsTradeRecord],
) -> list[GroupedPerformance]:
    groups: dict[str, list[AnalyticsTradeRecord]] = {}

    for trade in trades:
        groups.setdefault(trade["symbol"], []).append(trade)

    return sorted(
        (
            _summarize_trades(symbol, symbol, grouped_trades)
            for symbol, grouped_trades in groups.items()
        ),
        key=lambda group: group["net_pnl"],
        reverse=True,
    )


def summarize_by_strategy(
    trades: list[AnalyticsTradeRecord],
) -> list[GroupedPerformance]:
    groups: dict[str, dict[str, object]] = {}

    for trade in trades:
        strategies = trade.get("strategies") or []
        targets = strategies if strategies else [{"id": "unassigned", "name": "Unassigned"}]

        for strategy in targets:
            current = groups.get(strategy["id"], {"label": strategy["name"], "trades": []})
            current["trades"].append(trade)
            groups[strategy["id"]] = current

    return sorted(
        (
            _summarize_trades(key, str(group["label"]), group["trades"])
            for key, group in groups.items()
        ),
        key=lambda group: group["net_pnl"],
        reverse=True,
    )


def summarize_closed_trades(trades: list[ClosedTradeSummaryInput]) -> ClosedTradeSummary:
    cost_trades = [
        {
            "commission": trade.get("commission", 0.0),
            "swap": trade.get("swap", 0.0),
            "fees": trade.get("fees", 0.0),
        }
        for trade in trades
    ]
    holding_trades = [
        {"opened_at": trade["opened_at"], "closed_at": trade["closed_at"]}
        for trade in trades
        if trade.get("opened_at") is not None and trade.get("closed_at") is not None
    ]

    return {
        "net_pnl": calculate_net_pnl(trades),
        "gross_profit": calculate_gross_profit(trades),
        "gross_loss": calculate_gross_loss(trades),
        "win_count": count_wins(trades),
        "loss_count": count_losses(trades),
        "breakeven_count": count_breakeven(trades),
        "win_rate": calculate_win_rate(trades),
        "loss_rate": calculate_loss_rate(trades),
        "breakeven_rate": calculate_breakeven_rate(trades),
        "profit_factor": calculate_profit_factor(trades),
        "money_expectancy": calculate_money_expectancy(trades),
        "r_expectancy": calculate_r_expectancy(trades),
        "average_r": calculate_average_r(trades),
        "total_r": calculate_total_r(trades),
        "average_winner": calculate_average_winner(trades),
        "average_loser": calculate_average_loser(trades),
        "average_win_loss_ratio": calculate_average_win_loss_ratio(trades),
        "largest_winner": calculate_largest_winner(trades),
        "largest_loser": calculate_largest_loser(trades),
        "average_holding_time_minutes": calculate_average_holding_time_minutes(
            holding_trades
        ),
        "median_holding_time_minutes": calculate_median_holding_time_minutes(
            holding_trades
        ),
        "total_commission": calculate_total_commission(cost_trades),
        "total_swap": calculate_total_swap(cost_trades),
        "total_fees": calculate_total_fees(cost_trades),
        "total_trading_costs": calculate_total_trading_costs(cost_trades),
        "sample_confidence": get_sample_confidence(len(trades)),
    }
