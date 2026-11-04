"""Optional public venue precheck; unchanged deterministic risk still sets every ceiling."""

from __future__ import annotations

from decimal import Decimal

from tb.backtest.costs import CostAssumptions
from tb.ingest.venue_status import VenueBook, VenueRefused
from tb.risk.manager import EntryRequest, RejectionCode, RiskDecision, RiskManager, RiskState


def evaluate_entry_with_venue(
    manager: RiskManager,
    request: EntryRequest,
    state: RiskState,
    *,
    venue: VenueBook | None = None,
    historical: bool = False,
    costs: CostAssumptions | None = None,
) -> RiskDecision:
    """Veto new entries only; a TRADING fact merely delegates to authoritative risk."""
    if venue is not None:
        if historical:
            raise VenueRefused("venue_status_disabled_for_historical_backtests")
        decision = venue.venue_veto(request.symbol, request.timestamp)
        if decision.veto:
            return RiskDecision(
                approved=False,
                quantity=Decimal("0"),
                risk_amount=Decimal("0"),
                reason_code=RejectionCode.ASSET_POLICY,
                detail=decision.reason,
            )
    return manager.evaluate_entry(request, state, costs=costs)
