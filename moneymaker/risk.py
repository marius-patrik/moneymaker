"""Position sizing from % account risk. Balance is looked up fresh at
entry time (from whichever account/provider is active) so sizing stays
correct as an account's balance changes across trades."""

from __future__ import annotations


class RiskManager:
    def __init__(self, risk_pct: float = 0.01):
        self.risk_pct = risk_pct

    def position_size(self, account_balance: float, entry_price: float, stop_price: float) -> float:
        risk_amount = account_balance * self.risk_pct
        stop_distance = abs(entry_price - stop_price)
        if stop_distance <= 0:
            return 0.0
        return risk_amount / stop_distance
