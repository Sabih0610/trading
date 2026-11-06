# ADR 0031: separate causal daily/weekly medallion

Date: 2026-11-05. Status: proposed for Claude review under owner-authorized P11n.

Build daily/weekly derivatives from the three existing approved Silver datasets.
Keep the old Bronze, Silver, intraday Gold, source manifests, rights and original
retention unchanged. New outputs and pointers use a separate `swing-v1` namespace.
No market-data download or strategy evaluation is introduced.

UTC days are left-closed/right-open midnight windows; weeks begin Monday00:00 UTC.
At least95% of expected source minutes and no calendar conflict are required for
`complete`. Incomplete bars remain; missing prices/volume remain null. An expected-
zero closed period is metadata, not a fabricated complete signal bar.

The approved HistData source-week/US rollover clock remains the XAU base clock.
`config/swing-calendar.json` is a frozen **reference** holiday policy, not a claim
that another broker guarantees HistData sessions. It fixes exact UTC intervals,
New York conversion and evidence URLs before any genuine read. Actual observations
inside a declared closure remain present and flag `calendar_conflict`; they are
never deleted or used to tune the calendar. Unknown early closes stay conservative
coverage failures. This uncertainty must remain visible to P and Claude.

The shared FeatureEngine gains an explicit `update_swing` stream, with separate
bounded state. Its native/intraday output schema and calculations do not change.
SMA/EMA20/50/100/200, slopes, Wilder ATR14, prior-bar Donchian20/55, sample RV20
and strict confirmed swings are versioned. Swings require three left and three
later complete bars; the level is available at the confirmation bar's exclusive
end. P must not silently substitute a two-bar helper as the same feature.

Missing expected-open windows interrupt history. Closed expected-zero windows do
not. `coverage_available_at` is the exclusive ended-window timestamp even where
price `available_at` is null; a missing-window barrier is not visible before then.
The P bridge maps zero-observation missing windows to O's HistoryGap, partially
observed incomplete windows to incomplete CompletedBar, and omits empty closed
periods. No fake OHLC is created to satisfy a signal input type.

A private day-bound intrabar accessor admits current rights, source identity,
checksums and pre-holdout bounds before price reads. It returns immutable minutes
only for the bound completed UTC day; other-day and future-day requests refuse
before IO. Signal code receives no intrabar path. P's later engine adapter uses
it only for fill ordering; P remains behind its own registration approval.

Alternatives rejected: modifying registered intraday generations, accepting
incomplete bars as complete, filling missing OHLC, inferring holidays from absent
quotes, importing another broker's clock wholesale, or exposing intrabar paths to
signal helpers. All genuine observations and detailed coverage stay private.

Sources and options: [research](../research/P11n-research.md).
Authority: [N prompt](../../prompts/P11n-daily-weekly-data.md),
[master](../../prompts/MASTER-2026-12.md).
