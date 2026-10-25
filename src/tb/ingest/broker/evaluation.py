"""Readiness arithmetic and causal links only; never create simulation account state."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, StrictBool

from tb.core.instruments import CurrencyConversion, funded_notional
from tb.ingest.broker.models import (
    BrokerContract,
    BrokerQuote,
    BrokerRefused,
    Qualification,
    ReferenceQuoteLink,
)
from tb.ingest.rights import DataRights
from tb.risk.config import PolicyBundle, PolicyModel
from tb.shadow.models import ResearchDecision


class CostEvidence(PolicyModel):
    """Explicit scoped documentary cost reserve; raw rates alone are not a total."""

    account_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    contract_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    account_currency: str
    round_trip_reserve: Decimal = Field(ge=0)
    basis: str = Field(min_length=10)
    evidence_reference: str = Field(min_length=3)
    evidence: Literal["owned_fixture", "genuine"]
    verified: StrictBool = False
    observed_at: AwareDatetime
    expires_at: AwareDatetime


def qualify(
    contract: BrokerContract,
    quote: BrokerQuote | None,
    *,
    now: datetime,
    bundle: PolicyBundle,
    costs: CostEvidence | None = None,
    conversion: CurrencyConversion | None = None,
) -> Qualification:
    """Report $100 notional feasibility separately from all-in risk/simulation approval."""
    BrokerContract.model_validate(contract.model_dump())
    if costs is not None:
        costs = CostEvidence.model_validate(costs.model_dump())
    limits = bundle.risk.limits
    reasons = [
        "p11b2_not_authorized",
        "legal_eligibility_unverified",
        "independent_shariah_unverified",
        "all_in_planned_risk_not_assessed_no_simulation_candidate",
    ]
    fresh_contract = 0 <= (now - contract.observed_at).total_seconds() <= 86400
    market_ready = quote is not None
    if quote is not None:
        BrokerQuote.model_validate(quote.model_dump())
        market_ready = (
            fresh_contract
            and quote.metadata_digest == contract.digest
            and quote.account_fingerprint == contract.account_fingerprint
            and quote.symbol == contract.symbol
            and quote.symbol_id == contract.symbol_id
            and quote.evidence == contract.evidence
            and 0 <= (now - min(quote.bid_source_at, quote.ask_source_at)).total_seconds() <= 5
            and quote.received_at <= now
        )
    if not market_ready:
        reasons.append("admissible_fresh_broker_quote_unavailable")
    contract_ready = (
        fresh_contract
        and all(
            v is not None
            for v in (
                contract.lot_units,
                contract.min_units,
                contract.max_units,
                contract.step_units,
                contract.reported_tick_value_per_lot,
                contract.reported_tick_size,
                contract.profit_currency,
                contract.stop_distance,
                contract.distance_unit,
                contract.freeze_distance,
                contract.holidays,
            )
        )
        and bool(contract.schedule and contract.schedule_timezone)
        and contract.instrument_kind != "unknown"
    )
    if not contract_ready:
        reasons.append("contract_tick_value_product_session_or_constraint_facts_incomplete")
    cost_ready = bool(
        costs
        and costs.verified
        and costs.account_fingerprint == contract.account_fingerprint
        and costs.contract_digest == contract.digest
        and costs.account_currency == contract.account_currency
        and costs.evidence == contract.evidence
        and costs.observed_at <= now < costs.expires_at
    )
    if not cost_ready:
        reasons.append("cost_basis_commissions_conversion_and_funding_unverified")
    rate: Decimal | None = None
    if contract.account_currency == contract.quote_currency:
        rate = Decimal(1)  # Identity arithmetic, not an assumed market conversion rate.
    elif (
        conversion
        and conversion.account_currency == contract.account_currency
        and (
            conversion.quote_currency == contract.quote_currency
            and 0 <= (now - conversion.observed_at).total_seconds() <= 5
        )
    ):
        rate = conversion.rate
    else:
        reasons.append("fresh_account_currency_conversion_unverified")
    minimum: Decimal | None = None
    capital: Decimal | None = None
    affordable: bool | None = None
    if market_ready and quote and contract.min_units is not None and rate is not None:
        minimum = funded_notional(contract.min_units, quote.ask, rate)
        if cost_ready and costs:
            capital = minimum + costs.round_trip_reserve
        available = min(Decimal(100), Decimal(100) * limits.max_total_exposure_multiple)
        if minimum > available:
            affordable = False
            reasons.append("smallest_broker_position_exceeds_funded_100_before_costs")
        elif capital is not None:
            affordable = capital <= available
            if not affordable:
                reasons.append("smallest_broker_position_exceeds_funded_100_after_known_costs")
        else:
            reasons.append("minimum_notional_only_total_capital_unknown")
    return Qualification(
        symbol=contract.symbol,
        evidence=contract.evidence,
        market_data_ready=market_ready,
        contract_ready=contract_ready,
        costs_ready=cost_ready,
        funded_minimum_affordable=affordable,
        minimum_notional=minimum,
        minimum_capital_with_known_costs=capital,
        account_currency=contract.account_currency,
        reasons=tuple(reasons),
    )


def align_reference(
    decision: ResearchDecision,
    quote: BrokerQuote | None,
    *,
    now: datetime,
    reference_rights: DataRights,
) -> ReferenceQuoteLink:
    """Keep original decision availability; never infer a fill or fetch reference history."""
    ResearchDecision.model_validate(decision.model_dump())
    if reference_rights.digest != decision.rights_digest:
        raise BrokerRefused("reference_rights_version_mismatch")
    reference_rights.require(
        ("retrieval", "derived_storage"),
        provider=decision.provider,
        identity=reference_rights.account_fingerprint or "unconfigured",
        symbol=decision.symbol,
        now=now,
    )
    reason = "no_post_decision_broker_quote"
    valid = False
    if quote is not None:
        BrokerQuote.model_validate(quote.model_dump())
        if (decision.provider == "owned_fixture") != (quote.evidence == "owned_fixture"):
            reason = "reference_broker_evidence_mode_mismatch"
        elif quote.symbol != decision.symbol:
            reason = "reference_broker_instrument_mismatch"
        elif quote.received_at > now or decision.decision_at > now:
            reason = "reference_broker_future_availability"
        elif (
            min(
                quote.bid_source_at,
                quote.ask_source_at,
                quote.bid_received_at,
                quote.ask_received_at,
                quote.received_at,
            )
            < decision.decision_at
        ):
            reason = "broker_sides_precede_original_decision_availability"
        elif (now - min(quote.bid_source_at, quote.ask_source_at)).total_seconds() > 5:
            reason = "broker_quote_stale_at_alignment"
        elif (quote.received_at - decision.decision_at).total_seconds() > 30:
            reason = "broker_quote_alignment_delay_exceeded"
        elif decision.status != "candidate" or decision.signal == "WAIT":
            reason = "reference_decision_not_directional_candidate"
        else:
            valid, reason = True, "post_decision_indicative_observation_only"
    return ReferenceQuoteLink(
        reference_id=decision.id,
        reference_version=decision.strategy_version,
        reference_provider=decision.provider,
        symbol=decision.symbol,
        decision_at=decision.decision_at,
        quote_id=quote.event_id if valid and quote else None,
        quote_source_at=quote.source_at if valid and quote else None,
        quote_received_at=quote.received_at if valid and quote else None,
        delay_seconds=(quote.received_at - decision.decision_at).total_seconds()
        if valid and quote
        else None,
        spread=quote.spread if valid and quote else None,
        quote_age_seconds=quote.age_seconds if valid and quote else None,
        status="observed" if valid else "unavailable",
        reason=reason,
    )
