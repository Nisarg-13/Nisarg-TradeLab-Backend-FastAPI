from typing import TypedDict


class ConcentrationTrade(TypedDict):
    net_pnl: float


def _sum_top(values: list[float], count: int) -> float:
    return sum(sorted(values, reverse=True)[:count])


def _sum_worst(values: list[float], count: int) -> float:
    return sum(sorted(values)[:count])


def _percent_of_total(part: float, total: float) -> float | None:
    if total <= 0:
        return None

    return (part / total) * 100


class ProfitConcentrationSummary(TypedDict):
    winner_count: int
    gross_profit: float
    top1_percent: float | None
    top3_percent: float | None
    top5_percent: float | None
    top10_percent: float | None
    net_pnl_excluding_top1: float
    net_pnl_excluding_top3: float
    net_pnl_excluding_top5: float


class LossConcentrationSummary(TypedDict):
    loser_count: int
    gross_loss: float
    worst1_percent: float | None
    worst3_percent: float | None
    worst5_percent: float | None
    worst10_percent: float | None


class ConcentrationSummary(TypedDict):
    profit: ProfitConcentrationSummary
    loss: LossConcentrationSummary


def summarize_profit_concentration(
    trades: list[ConcentrationTrade],
) -> ProfitConcentrationSummary:
    winners = [trade["net_pnl"] for trade in trades if trade["net_pnl"] > 0]

    gross_profit = sum(winners)
    net_pnl = sum(trade["net_pnl"] for trade in trades)

    top1 = _sum_top(winners, 1)
    top3 = _sum_top(winners, 3)
    top5 = _sum_top(winners, 5)
    top10 = _sum_top(winners, 10)

    return {
        "winner_count": len(winners),
        "gross_profit": gross_profit,
        "top1_percent": _percent_of_total(top1, gross_profit),
        "top3_percent": _percent_of_total(top3, gross_profit),
        "top5_percent": _percent_of_total(top5, gross_profit),
        "top10_percent": _percent_of_total(top10, gross_profit),
        "net_pnl_excluding_top1": net_pnl - top1,
        "net_pnl_excluding_top3": net_pnl - top3,
        "net_pnl_excluding_top5": net_pnl - top5,
    }


def summarize_loss_concentration(
    trades: list[ConcentrationTrade],
) -> LossConcentrationSummary:
    losers = [trade["net_pnl"] for trade in trades if trade["net_pnl"] < 0]

    gross_loss = abs(sum(losers))

    worst1 = abs(_sum_worst(losers, 1))
    worst3 = abs(_sum_worst(losers, 3))
    worst5 = abs(_sum_worst(losers, 5))
    worst10 = abs(_sum_worst(losers, 10))

    return {
        "loser_count": len(losers),
        "gross_loss": gross_loss,
        "worst1_percent": _percent_of_total(worst1, gross_loss),
        "worst3_percent": _percent_of_total(worst3, gross_loss),
        "worst5_percent": _percent_of_total(worst5, gross_loss),
        "worst10_percent": _percent_of_total(worst10, gross_loss),
    }


def summarize_concentration(trades: list[ConcentrationTrade]) -> ConcentrationSummary:
    return {
        "profit": summarize_profit_concentration(trades),
        "loss": summarize_loss_concentration(trades),
    }
