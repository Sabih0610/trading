# ADR 0004: Separate research contracts and account safety

Date: 2026-10-22. Status: accepted for P09.5 under the owner's attached brief.

The primary research targets are now XAUUSD/EURUSD. Binance spot remains a secondary research
track. External execution is out of scope, and existing Spot-only and inventory-sale guards stay.

Add explicit reference, historical, local simulation, broker-demo and live eligibility. Research
permission does not certify ownership, Shariah status or brokerage permission. All external-order
eligibility is disabled in this phase, including if a configuration attempts to enable it.

Gold/FX contract simulations reserve their entire gross notional plus fees. Metadata is explicit,
timestamped and checked at use. Fixture contracts are visibly synthetic and cannot be represented
as authenticated broker facts. A $100 account must reject ordinary minimum lots it cannot fund.

Use marked liquidation equity for 2% daily and 5% peak loss protection. Halts latch, and the peak
halt survives day rollover. Size planned stops including costs under the 0.5% configured default.
Recheck risk at actual fills to account for gaps. These are planned-loss ceilings, not a guarantee
that a discontinuous market cannot lose more.

Preserve the 2025+ holdout. Inception-aware assessment reports insufficient eligible XAUT history
instead of moving the lock or impersonating XAUT with a gold reference feed.

See [research](../research/P09.5-research.md). Future broker routing needs a separately reviewed
phase and independently verified demo identity. No real-money route is created here.
