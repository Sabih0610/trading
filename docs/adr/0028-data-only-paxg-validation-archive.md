# ADR 0028: data-only PAXG validation archive

Date: 2026-11-04. Status: accepted for the owner-authorized acquisition boundary;
strategy validation still requires its separate pre-registration review.

The owner withdrew Dukascopy consent and approved thirteen PAXGUSDT monthly 1m
archives from Binance Vision. PAXG is a reference instrument only. The existing
executable archive URL builder rejects data-only instruments and must keep doing so.

Keep that guard unchanged. The rights-admitted Vision acquisition function may
construct a fixed PAXG monthly kline URL after validating the exact dataset ID,
single-symbol scope, interval and UTC bounds. Reuse all existing retention,
evidence-hash, checksum, immutable Bronze and bounded yearly feature publication
checks. Data Health reads only the admitted 2023/2024 JSON metadata.

A broader executable allowlist was rejected because retrieval permission is not
trading permission. Arbitrary PAXG history or alternate intervals were rejected:
2024 must remain an untouched validation year, and December 2023 is warm-up only.

No price analysis, chart or strategy run follows from acquisition. After G Part B
merges, a promising candidate and approved K registration are both required for a
single validation run with frozen parameters. Any result is on the PAXG proxy,
never on XAUT. All genuine data and detailed derived artifacts remain private.

Authority: [rights review](../../reports/reviews/dataset-rights-review-2026-11-04.md),
[research](../research/P11k-research.md), [master](../../prompts/MASTER-2026-11.md).
