from app.calculators.risk.direction import (
    calculate_price_distance,
    validate_stop_loss,
    validate_take_profit,
)
from app.calculators.risk.position_size import (
    calculate_loss_per_lot,
    calculate_profit_per_lot,
    calculate_raw_volume,
    clamp_volume,
    round_volume_down,
)
from app.calculators.risk.risk_amount import calculate_risk_amount, calculate_risk_percentage
from app.calculators.risk.risk_reward import calculate_reward_distance, calculate_risk_reward
from app.calculators.risk.types import (
    CalculateRiskInput,
    CalculateRiskResult,
    RiskViolation,
)

BLOCKING_VIOLATION_CODES = {
    "INVALID_STOP_LOSS",
    "INVALID_TAKE_PROFIT",
    "VOLUME_BELOW_MINIMUM",
    "MAX_RISK_PER_TRADE",
    "MAX_DAILY_RISK",
    "MAX_DAILY_LOSS",
    "MAX_OPEN_RISK",
    "MAX_TRADES_PER_DAY",
    "MAX_CONSECUTIVE_LOSSES",
}


def calculate_risk(input_data: CalculateRiskInput) -> CalculateRiskResult:
    violations: list[RiskViolation] = []
    price_distance = calculate_price_distance(
        input_data["entryPrice"],
        input_data["stopLoss"],
        input_data["instrument"]["tickSize"],
    )

    if not validate_stop_loss(
        input_data["direction"],
        input_data["entryPrice"],
        input_data["stopLoss"],
    ):
        violations.append(
            {
                "severity": "critical",
                "code": "INVALID_STOP_LOSS",
                "message": (
                    "Stop loss must be below entry for a long trade."
                    if input_data["direction"] == "LONG"
                    else "Stop loss must be above entry for a short trade."
                ),
            }
        )

    if (
        "takeProfit" in input_data
        and input_data["takeProfit"] is not None
        and not validate_take_profit(
            input_data["direction"],
            input_data["entryPrice"],
            input_data["takeProfit"],
        )
    ):
        violations.append(
            {
                "severity": "critical",
                "code": "INVALID_TAKE_PROFIT",
                "message": (
                    "Take profit must be above entry for a long trade."
                    if input_data["direction"] == "LONG"
                    else "Take profit must be below entry for a short trade."
                ),
            }
        )

    risk_amount = calculate_risk_amount(
        input_data["riskMode"],
        input_data["accountBalance"],
        input_data.get("riskPercentage"),
        input_data.get("fixedRiskAmount"),
    )

    if risk_amount <= 0:
        violations.append(
            {
                "severity": "critical",
                "code": "INVALID_RISK_AMOUNT",
                "message": "Risk amount must be greater than zero.",
            }
        )

    has_invalid_stop = any(
        violation["code"] == "INVALID_STOP_LOSS" for violation in violations
    )
    has_invalid_take_profit = any(
        violation["code"] == "INVALID_TAKE_PROFIT" for violation in violations
    )

    risk_percentage = calculate_risk_percentage(
        risk_amount,
        input_data["accountBalance"],
    )

    recommended_position_size = 0.0
    potential_loss = 0.0
    potential_profit: float | None = None
    loss_per_lot = 0.0

    if not has_invalid_stop and risk_amount > 0:
        loss_per_lot = calculate_loss_per_lot(
            price_distance,
            input_data["instrument"],
            input_data["entryPrice"],
        )
        raw_volume = calculate_raw_volume(risk_amount, loss_per_lot)
        rounded_volume = round_volume_down(
            raw_volume,
            input_data["instrument"]["volumeStep"],
        )
        recommended_position_size = clamp_volume(
            rounded_volume,
            input_data["instrument"],
        )

        if (
            recommended_position_size <= 0
            or recommended_position_size < input_data["instrument"]["volumeMin"]
        ):
            violations.append(
                {
                    "severity": "critical",
                    "code": "VOLUME_BELOW_MINIMUM",
                    "message": (
                        "Recommended position size is below the minimum volume of "
                        f"{input_data['instrument']['volumeMin']} lots."
                    ),
                }
            )
        elif raw_volume > input_data["instrument"]["volumeMax"]:
            violations.append(
                {
                    "severity": "warning",
                    "code": "VOLUME_ABOVE_MAXIMUM",
                    "message": (
                        "Calculated volume exceeds the maximum of "
                        f"{input_data['instrument']['volumeMax']} lots and was capped."
                    ),
                }
            )

        potential_loss = loss_per_lot * recommended_position_size

        if (
            "takeProfit" in input_data
            and input_data["takeProfit"] is not None
            and not has_invalid_take_profit
        ):
            reward_distance = calculate_reward_distance(
                input_data["direction"],
                input_data["entryPrice"],
                input_data["takeProfit"],
                input_data["instrument"]["tickSize"],
            )
            potential_profit = (
                calculate_profit_per_lot(
                    reward_distance,
                    input_data["instrument"],
                    input_data["entryPrice"],
                )
                * recommended_position_size
            )

    risk_reward = (
        None
        if has_invalid_stop or has_invalid_take_profit
        else calculate_risk_reward(
            input_data["direction"],
            input_data["entryPrice"],
            input_data["stopLoss"],
            input_data.get("takeProfit"),
            input_data["instrument"]["tickSize"],
        )
    )

    current_daily_risk = input_data["riskContext"]["currentDailyRiskAmount"]
    daily_risk_after_trade = current_daily_risk + potential_loss
    current_open_risk = input_data["riskContext"]["currentOpenRiskAmount"]
    open_risk_after_trade = current_open_risk + potential_loss

    if input_data.get("evaluateAccountRules", True):
        _evaluate_risk_rules(
            input_data,
            {
                "riskPercentage": risk_percentage,
                "potentialLoss": potential_loss,
                "dailyRiskAfterTrade": daily_risk_after_trade,
                "openRiskAfterTrade": open_risk_after_trade,
                "violations": violations,
            },
        )

    blocked = input_data["riskSettings"]["strictMode"] and any(
        violation["code"] in BLOCKING_VIOLATION_CODES for violation in violations
    )

    return {
        "accountBalance": input_data["accountBalance"],
        "riskPercentage": risk_percentage,
        "riskAmount": risk_amount,
        "priceDistance": price_distance,
        "stopDistance": price_distance,
        "recommendedPositionSize": recommended_position_size,
        "potentialLoss": potential_loss,
        "potentialProfit": potential_profit,
        "riskReward": risk_reward,
        "currentDailyRisk": current_daily_risk,
        "dailyRiskAfterTrade": daily_risk_after_trade,
        "currentOpenRisk": current_open_risk,
        "openRiskAfterTrade": open_risk_after_trade,
        "violations": violations,
        "blocked": blocked,
    }


def _evaluate_risk_rules(
    input_data: CalculateRiskInput,
    state: dict[str, object],
) -> None:
    risk_settings = input_data["riskSettings"]
    account_balance = input_data["accountBalance"]
    risk_context = input_data["riskContext"]
    violations = state["violations"]
    assert isinstance(violations, list)

    max_risk_per_trade_amount = (
        account_balance * risk_settings["maxRiskPerTradePercentage"]
    ) / 100
    max_daily_risk_amount = (
        account_balance * risk_settings["maxDailyRiskPercentage"]
    ) / 100
    max_daily_loss_amount = (
        account_balance * risk_settings["maxDailyLossPercentage"]
    ) / 100
    max_open_risk_amount = (
        account_balance * risk_settings["maxOpenRiskPercentage"]
    ) / 100

    risk_percentage = state["riskPercentage"]
    potential_loss = state["potentialLoss"]
    daily_risk_after_trade = state["dailyRiskAfterTrade"]
    open_risk_after_trade = state["openRiskAfterTrade"]
    assert isinstance(risk_percentage, float)
    assert isinstance(potential_loss, float)
    assert isinstance(daily_risk_after_trade, float)
    assert isinstance(open_risk_after_trade, float)

    if risk_percentage > risk_settings["maxRiskPerTradePercentage"]:
        violations.append(
            {
                "severity": "warning",
                "code": "MAX_RISK_PER_TRADE",
                "message": (
                    "Risk exceeds the configured maximum of "
                    f"{risk_settings['maxRiskPerTradePercentage']}% per trade."
                ),
            }
        )

    if potential_loss > max_risk_per_trade_amount:
        violations.append(
            {
                "severity": "warning",
                "code": "MAX_RISK_PER_TRADE",
                "message": (
                    "Potential loss exceeds the configured maximum of "
                    f"{max_risk_per_trade_amount:.2f} for this account."
                ),
            }
        )

    if daily_risk_after_trade > max_daily_risk_amount:
        violations.append(
            {
                "severity": "warning",
                "code": "MAX_DAILY_RISK",
                "message": "Daily risk would exceed the configured limit.",
            }
        )

    if risk_context["currentDailyLossAmount"] >= max_daily_loss_amount:
        violations.append(
            {
                "severity": "warning",
                "code": "MAX_DAILY_LOSS",
                "message": "Maximum daily loss limit has already been reached.",
            }
        )

    if open_risk_after_trade > max_open_risk_amount:
        violations.append(
            {
                "severity": "warning",
                "code": "MAX_OPEN_RISK",
                "message": "Open risk would exceed the configured limit.",
            }
        )

    if risk_context["tradesTodayCount"] >= risk_settings["maxTradesPerDay"]:
        violations.append(
            {
                "severity": "warning",
                "code": "MAX_TRADES_PER_DAY",
                "message": "Maximum number of trades for today has been reached.",
            }
        )

    if risk_context["consecutiveLossesCount"] >= risk_settings["maxConsecutiveLosses"]:
        violations.append(
            {
                "severity": "warning",
                "code": "MAX_CONSECUTIVE_LOSSES",
                "message": "Maximum consecutive loss rule has been reached.",
            }
        )
