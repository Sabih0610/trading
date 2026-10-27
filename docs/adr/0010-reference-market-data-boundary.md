# 0010 — Reference market data remains separate from execution quotes

Accepted 2026-10-23 for P11a.3. Twelve Data is an optional GET-only reference provider.
Reuse the immutable store and classifier; add reference records with nullable broker fields.
Never synthesize bid/ask, volume, fees, contract metadata or fills from midpoints.

The adapter implements the existing ReadOnlyMarketFeed contract, with contract/quotes calls
explicitly refused because executable facts are unavailable. Its provider-specific bounded
runner handles references and M1 bars without changing the MT5 polling cadence or profiles.
Documented UTC representation is validated directly, with no broker clock offset or profile
promotion. Freshness allows the documented minute update cadence; point-source age remains
distinct from bar-open age and completion/publication delay.

Daily and minute API reservations persist across crashes, keyed by a nonreversible credential
fingerprint. Actual upstream usage can reduce remaining budget; ambiguous failures still
consume a reservation. No automatic paid plan, unlimited retries or endpoint expansion.

Basic's non-display label is enforced in the UI: provider/clock/qualification/counts visible,
market prices withheld until rights are established. Raw responses and local price exports
remain in ignored storage. Long-term/commercial retention and execution realism remain NO-GO.
Original MT5/OANDA data and historical authorization are untouched. P11b is not implemented.
