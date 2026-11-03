# Spot venue status monitor and entry veto

This opt-in component reads public Spot status metadata for XAUTUSDT, BTCUSDT,
ETHUSDT and SOLUSDT. It stores transitions privately and exposes a pure entry-only
veto. It has no key, price-feed, order or exit capability and is off by default
in all existing entry paths.

## Run the monitor

Use its separate credential-free checkout, with no `.env` at the checkout root:

```powershell
uv sync --locked
uv run --locked python -m tb.ingest.venue_status --interval 60
```

For a bounded operational check, add `--seconds 70`. Ctrl+C stops cleanly. The
minimum interval is 60 seconds. Retry-After is retained across restarts; three
failed attempts produce a cooldown of at least ten minutes. There is no burst
retry loop, redirection, authenticated client or unbounded response stream.

Private outputs: `work/venue_status/status.sqlite` holds append-only changes and
the small current receipt/poll-control state. `reports/data_quality/venue-status-health.json`
is a private operational projection for Data Health. Keep both ignored; never
copy genuine status observations into a PR. No scheduled task or live paper run
is installed by this component.

## Use the veto

Load an immutable `VenueBook` from the private store, then query
`book.venue_veto(symbol, at)` with an aware UTC decision clock. Unknown, non-TRADING,
future-only or >10-minute-old status vetoes the entry. Exactly ten minutes is
still fresh. A TRADING result is only permission to continue to the unchanged
deterministic risk manager through `evaluate_entry_with_venue`; it never grants
a risk exception or supplies quantity.

The optional `venue_veto` input on shared paper sizing is checked for matching
symbol/decision clock and can only reject. Local simulation rechecks at proposal
and next event. Owned Paper Lab events accept fixture-tagged facts only; this
does not authorize genuine price/paper integration. Existing exits do not consult
the veto. Historical contract replay refuses an enabled venue book, and the
historical BacktestEngine is unchanged and has no status input.

## Observe and troubleshoot

Data Health shows current status, receipt time and last change, recomputing age
at read time. It never polls. If the monitor is missing, malformed or stale, the
status is unknown/stale and new entries fail closed. The health JSON includes a
static last-error category, retry deadline and failure counter. No full response
body or secrets are logged.

The transition journal and heartbeat have different purposes: repeated successful
TRADING polls refresh receipt time without adding rows to the change history.
This is a current control source, not a complete historical availability tape.

Official terms notice observed 2026-11-03: modified 2026-10-30; full Product Terms
version unverified, matching the reviewed open item. See [research](../research/P11h-research.md),
[ADR](../adr/0023-venue-status-entry-veto.md), and [report](../../reports/phases/P11h.md).
