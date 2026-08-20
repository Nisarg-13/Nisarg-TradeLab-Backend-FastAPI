from .types import RiskMode


def calculate_risk_amount(
    risk_mode: RiskMode,
    account_balance: float,
    risk_percentage: float | None = None,
    fixed_risk_amount: float | None = None,
) -> float:
    if risk_mode == "PERCENTAGE":
        if risk_percentage is None or risk_percentage <= 0:
            return 0

        return (account_balance * risk_percentage) / 100

    return fixed_risk_amount if fixed_risk_amount and fixed_risk_amount > 0 else 0


def calculate_risk_percentage(risk_amount: float, account_balance: float) -> float:
    if account_balance <= 0:
        return 0

    return (risk_amount / account_balance) * 100
