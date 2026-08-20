from fastapi import HTTPException, status

from app.calculators.risk.calculate_risk import calculate_risk
from app.calculators.risk.constants import (
    DEFAULT_RISK_SETTINGS,
    find_catalog_instrument,
    list_catalog_instruments,
)
from app.schemas.risk import CalculateRiskBody, CalculateRiskResponse, RiskViolationResponse


class RiskService:
    @staticmethod
    def list_instruments() -> list[dict[str, object]]:
        return list_catalog_instruments()

    @staticmethod
    def calculate(input_data: CalculateRiskBody) -> CalculateRiskResponse:
        instrument = find_catalog_instrument(input_data.symbol)

        if not instrument:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported instrument symbol: {input_data.symbol}",
            )

        result = calculate_risk(
            {
                "accountBalance": input_data.account_balance,
                "instrument": {
                    "symbol": instrument["symbol"],
                    "contractSize": float(instrument["contract_size"]),
                    "tickSize": float(instrument["tick_size"]),
                    "tickValueProfit": float(instrument["tick_value_profit"]),
                    "tickValueLoss": float(instrument["tick_value_loss"]),
                    "volumeMin": float(instrument["volume_min"]),
                    "volumeMax": float(instrument["volume_max"]),
                    "volumeStep": float(instrument["volume_step"]),
                },
                "direction": input_data.direction.value,
                "entryPrice": input_data.entry_price,
                "stopLoss": input_data.stop_loss,
                "takeProfit": input_data.take_profit,
                "riskMode": input_data.risk_mode,
                "riskPercentage": input_data.risk_percentage,
                "fixedRiskAmount": input_data.fixed_risk_amount,
                "evaluateAccountRules": False,
                "riskSettings": DEFAULT_RISK_SETTINGS,
                "riskContext": {
                    "currentDailyRiskAmount": 0,
                    "currentDailyLossAmount": 0,
                    "currentOpenRiskAmount": 0,
                    "tradesTodayCount": 0,
                    "consecutiveLossesCount": 0,
                },
            }
        )

        return CalculateRiskResponse(
            symbol=instrument["symbol"],
            direction=input_data.direction,
            entryPrice=str(input_data.entry_price),
            stopLoss=str(input_data.stop_loss),
            takeProfit=str(input_data.take_profit) if input_data.take_profit is not None else None,
            riskMode=input_data.risk_mode,
            accountBalance=str(result["accountBalance"]),
            riskPercentage=str(result["riskPercentage"]),
            riskAmount=str(result["riskAmount"]),
            priceDistance=str(result["priceDistance"]),
            stopDistance=str(result["stopDistance"]),
            recommendedPositionSize=str(result["recommendedPositionSize"]),
            potentialLoss=str(result["potentialLoss"]),
            potentialProfit=(
                str(result["potentialProfit"]) if result["potentialProfit"] is not None else None
            ),
            riskReward=str(result["riskReward"]) if result["riskReward"] is not None else None,
            currentDailyRisk=str(result["currentDailyRisk"]),
            dailyRiskAfterTrade=str(result["dailyRiskAfterTrade"]),
            currentOpenRisk=str(result["currentOpenRisk"]),
            openRiskAfterTrade=str(result["openRiskAfterTrade"]),
            violations=[
                RiskViolationResponse(
                    severity=violation["severity"],
                    code=violation["code"],
                    message=violation["message"],
                )
                for violation in result["violations"]
            ],
            blocked=result["blocked"],
        )
