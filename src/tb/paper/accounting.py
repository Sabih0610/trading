"""Shared full-cash flows for legacy and persistent local contract simulations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tb.core.instruments import ContractSpec


@dataclass(frozen=True)
class CashFlow:
    """Gross full notional, explicit fee and net account cash movement."""

    gross: Decimal
    fee: Decimal
    cash: Decimal


def funded_flow(
    spec: ContractSpec, lots: Decimal, price: Decimal, rate: Decimal, *, entry: bool
) -> CashFlow:
    """Fees are charged once; liquidation value includes modeled exit fees."""
    if not lots.is_finite() or lots <= 0:
        raise ValueError("Positive finite owned lots required")
    gross = spec.notional(lots, price, rate)
    fee = gross * spec.fee_bps / 10000
    return CashFlow(gross, fee, -(gross + fee) if entry else gross - fee)
