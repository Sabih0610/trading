# Multi-day holding policy and owned verification

The owner permits overnight positions for at most ten calendar days. Human config may lower the bound; a proposal cannot increase it. Every existing intraday proposal still defaults to EOD flattening. This software change does not authorize operational paper, Testnet or orders.

In `config/risk.yaml`, `max_holding_days` is a strict integer1..10 and defaults10. `flat_by_end_of_day` defaultsFalse globally. A strategy opts into overnight holding only by proposing `flat_by_end_of_day=False`; globalTrue always wins. Stops,2% daily marked-equity loss,5% peak drawdown,0.5% planned risk,1x exposure, one position and XAUT weekend entry restrictions are unchanged.

The holding clock starts at the actual fill. The first observed valid event at or after entry+effectiveDays closes the position. Calendar/weekend gaps do not add permitted days; absent/stale quotes cannot be invented. Existing intraday and strategy time exits may close earlier. Daily loss compares current net-liquidation equity with the last valid mark of the prior UTC day, including overnight changes.

From a credential-free checkout, verify owned mechanics only:

```powershell
uv sync --locked
uv run --locked pytest -q './tests/unit/test_multi_day_holding.py' './tests/unit/test_multi_day_eod_compatibility.py' './tests/integration/test_multi_day_paper.py'
```

Coordinate the machine's test slot before running. The required full credential-free gate is `pwsh -NoProfile -File './scripts/check-offline.ps1'`; never run two full suites concurrently.

## Metadata during owned multi-day tests

The original24h spec/broker metadata freshness bound remains. Explicit owned refresh inputs must contain an independently supplied fresh observation, a unique owned observation ID, prior digest and known_at. The full contract identity, costs, units, currency, account and session facts must remain identical; source timestamps must be newer and known by the event clock. No helper fetches provider data or renews rights.

`LocalPaperSimulator.run(..., metadata_refreshes=...)` accepts only OwnedSpecRefresh observations aligned with observed quotes. Offline PaperInput kindmetadata carries PaperContractRefresh; its overrides, known_at chain and seen IDs are persisted in the same atomic journal/checkpoint transaction. An old quote is removed when metadata changes; a subsequent valid quote is required. Exact duplicate events deduplicate; reusing an observation ID for different input refuses.

No refresh means stale metadata fails closed, even at the holding deadline. Do not disable freshness, fabricate new timestamps or reset a store to hide the refusal. Existing package/source/risk/schema mismatch still refuses recovery; preserve the old store. Any real provider or future paper integration needs separate authority and lawful current metadata.

The regression fixture `tests/fixtures/owned_legacy_eod.json` is entirely fictional: constant100 prices, pre-change EOD behavior for BTC/XAUT, no genuine data. It proves full financial-output equality without running any frozen genuine F/G batch.

See [ADR0030](../adr/0030-multi-day-holding.md), [phase](../../reports/phases/P11m.md) and [journal](../journal/P11m-journal.md).
