from typing import TypedDict

from app.calculators.risk.position_size import (
    calculate_loss_per_lot,
    calculate_profit_per_lot,
)
from app.calculators.risk.types import TradeDirection


class InstrumentPricing(TypedDict):
    contractSize: float
    tickSize: float
    tickValueProfit: float
    tickValueLoss: float


class ExecutionTotalsRow(TypedDict):
    profit: float
    commission: float
    swap: float
    fee: float


class ExecutionTotals(TypedDict):
    grossPnl: float
    commission: float
    swap: float
    fees: float
    netPnl: float


def calculate_execution_profit(
    direction: TradeDirection,
    entry_price: float,
    exit_price: float,
    volume: float,
    instrument: InstrumentPricing,
) -> float:
    price_distance = (
        exit_price - entry_price
        if direction == "LONG"
        else entry_price - exit_price
    )

    if price_distance == 0:
        return 0

    if price_distance < 0:
        loss_per_lot = calculate_loss_per_lot(
            abs(price_distance),
            instrument,
            entry_price,
        )

        return -(loss_per_lot * volume)

    profit_per_lot = calculate_profit_per_lot(
        price_distance,
        instrument,
        entry_price,
    )

    return profit_per_lot * volume


def calculate_unrealized_profit(
    direction: TradeDirection,
    average_entry_price: float,
    mark_price: float,
    volume: float,
    instrument: InstrumentPricing,
) -> float:
    return calculate_execution_profit(
        direction,
        average_entry_price,
        mark_price,
        volume,
        instrument,
    )


def calculate_risk_at_price(
    direction: TradeDirection,
    entry_price: float,
    stop_loss: float,
    volume: float,
    instrument: InstrumentPricing,
) -> float:
    price_distance = (
        entry_price - stop_loss
        if direction == "LONG"
        else stop_loss - entry_price
    )

    if price_distance <= 0:
        return 0

    loss_per_lot = calculate_loss_per_lot(price_distance, instrument, entry_price)

    return loss_per_lot * volume


def sum_execution_totals(executions: list[ExecutionTotalsRow]) -> ExecutionTotals:
    gross_pnl = sum(row["profit"] for row in executions)
    commission = sum(row["commission"] for row in executions)
    swap = sum(row["swap"] for row in executions)
    fees = sum(row["fee"] for row in executions)

    return {
        "grossPnl": gross_pnl,
        "commission": commission,
        "swap": swap,
        "fees": fees,
        "netPnl": gross_pnl - commission - swap - fees,
    }
