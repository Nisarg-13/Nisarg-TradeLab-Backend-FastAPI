from datetime import datetime
from typing import TypedDict

from app.calculators.risk.types import ExecutionType, TradeDirection, TradeStatus
from app.calculators.trades.realized_r import calculate_realized_r
from app.calculators.trades.trade_pnl import (
    InstrumentPricing,
    calculate_execution_profit,
    sum_execution_totals,
)
from app.calculators.trades.weighted_price import (
    VolumePriceRow,
    calculate_weighted_average_price,
    sum_volume,
)


class ExecutionInput(TypedDict, total=False):
    type: ExecutionType
    price: float
    volume: float
    profit: float
    commission: float
    swap: float
    fee: float
    executedAt: datetime


class RecalculateTradeStateInput(TypedDict):
    direction: TradeDirection
    initialRiskAmount: float | None
    instrument: InstrumentPricing
    executions: list[ExecutionInput]


class RecalculatedTradeState(TypedDict):
    averageEntryPrice: float
    averageExitPrice: float | None
    initialVolume: float
    currentVolume: float
    grossPnl: float
    commission: float
    swap: float
    fees: float
    netPnl: float
    realizedR: float | None
    status: TradeStatus
    closedAt: datetime | None


def recalculate_trade_state(
    input_data: RecalculateTradeStateInput,
) -> RecalculatedTradeState:
    entry_rows: list[VolumePriceRow] = [
        {"price": execution["price"], "volume": execution["volume"]}
        for execution in input_data["executions"]
        if execution["type"] == "ENTRY"
    ]

    exit_rows: list[VolumePriceRow] = [
        {"price": execution["price"], "volume": execution["volume"]}
        for execution in input_data["executions"]
        if execution["type"] == "EXIT"
    ]

    average_entry_price = calculate_weighted_average_price(entry_rows)
    average_exit_price = (
        calculate_weighted_average_price(exit_rows) if len(exit_rows) > 0 else None
    )

    initial_volume = sum_volume(entry_rows)
    exited_volume = sum_volume(exit_rows)
    current_volume = max(initial_volume - exited_volume, 0)

    priced_executions = []
    for execution in input_data["executions"]:
        if execution["type"] == "ENTRY":
            priced_executions.append(
                {
                    "profit": 0,
                    "commission": execution.get("commission", 0),
                    "swap": execution.get("swap", 0),
                    "fee": execution.get("fee", 0),
                }
            )
            continue

        profit = (
            execution["profit"]
            if "profit" in execution
            else calculate_execution_profit(
                input_data["direction"],
                average_entry_price,
                execution["price"],
                execution["volume"],
                input_data["instrument"],
            )
        )

        priced_executions.append(
            {
                "profit": profit,
                "commission": execution.get("commission", 0),
                "swap": execution.get("swap", 0),
                "fee": execution.get("fee", 0),
            }
        )

    totals = sum_execution_totals(priced_executions)
    realized_r = calculate_realized_r(
        totals["netPnl"],
        input_data["initialRiskAmount"],
    )

    last_execution = input_data["executions"][-1] if input_data["executions"] else None
    is_closed = current_volume <= 0 and len(exit_rows) > 0

    return {
        "averageEntryPrice": average_entry_price,
        "averageExitPrice": average_exit_price,
        "initialVolume": initial_volume,
        "currentVolume": current_volume,
        "grossPnl": totals["grossPnl"],
        "commission": totals["commission"],
        "swap": totals["swap"],
        "fees": totals["fees"],
        "netPnl": totals["netPnl"],
        "realizedR": realized_r,
        "status": "CLOSED" if is_closed else "OPEN",
        "closedAt": (
            last_execution["executedAt"]
            if is_closed and last_execution is not None
            else None
        ),
    }
