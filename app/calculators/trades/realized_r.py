def calculate_realized_r(
    net_pnl: float,
    initial_risk_amount: float | None,
) -> float | None:
    if initial_risk_amount is None or initial_risk_amount <= 0:
        return None

    return net_pnl / initial_risk_amount
