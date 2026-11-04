# P11k: acquire the approved PAXG validation proxy

The owner and distinct reviewer approved PAXGUSDT Vision monthly 1m archives for
private validation research, replacing withdrawn Dukascopy consent. Acquisition
and medallion construction may proceed now. Strategy evaluation and price display
remain unavailable until a separate K registration is approved.

| Question | Options | Decision |
|---|---|---|
| How to acquire a data-only asset? | Widen executable archive guard; isolated admitted Vision URL | Keep executable guard unchanged; construct only the fixed PAXG monthly kline URL after exact plan admission. |
| How much history? | All available PAXG; approved window | Exactly December 2023 through December 2024, 13 monthly archives; December 2023 is warm-up only. |
| Integrity and storage? | New downloader; existing medallion | Reuse sequential ZIP/CHECKSUM verification, immutable Bronze, bounded yearly Silver/Gold and current rights/retention checks. |
| Inspect progress? | Price charts; metadata | Data Health reads JSON manifests and quality metadata only. |

Sources accessed 2026-11-04:

- [Binance public-data documentation](https://github.com/binance/binance-public-data):
  monthly Spot klines, twelve-field schema, checksum sidecars, and possible archive
  revisions support the existing immutable downloader. Its 2025 microsecond change
  does not permit requesting any 2025 archive here.
- [Owner and reviewer rights decision](../../reports/reviews/dataset-rights-review-2026-11-04.md):
  exact instrument/window, data-only role, existing terms PDF evidence and retention
  through 2028-11-01.
- [Original documentary terms review](../../reports/reviews/dataset-rights-review-2026-11-01.md):
  private research and no redistribution or live use under the current permission.

The proxy can have a premium/discount to spot gold and does not establish XAUT
liquidity. No strategy validation or gold verdict is inferred from acquisition.
The existing pinned Python 3.12, HTTPX, Polars and FeatureEngine remain in use;
no dependency or risk-limit change is required.

Architecture: [ADR 0028](../adr/0028-data-only-paxg-validation-archive.md).
