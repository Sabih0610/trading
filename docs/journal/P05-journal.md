# P05 journal — feature engine

P05 is building one deterministic, causal feature implementation shared by batch research and
bar-by-bar paper/live evaluation. Every feature will declare its inputs, warmup, confirmation lag,
timeframe, and version; unavailable licensed or historical inputs remain explicitly null.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 01:39 UTC | Context | Read P05, P04 report/handoff/state, the mandatory project rules, and the quant-analysis skill. | `prompts/P05-feature-engine.md`, `.agents/skills/` | P05 started from the tagged P04 checkpoint. Quant guidance is limited to deterministic spot-safe feature methodology. | — |
| 2026-10-21 01:40 UTC | Research | Searched current Polars, Binance Spot, TradingView pivot, and online-algorithm references for causal rolling windows, confirmed pivots, local order books, and batch/stream parity. | `docs/research/P05-research.md` | Research in progress; subjective structure terms will receive explicit project definitions and confirmation delays. | — |
| 2026-10-21 01:43 UTC | Shared core | Added versioned feature metadata and one streaming state for ATR, realized volatility, EMAs/slopes, confirmed pivots, structure breaks, VWAP, and session levels; batch replays it. | `src/tb/features/engine.py`, `tests/unit/test_feature_engine.py` | 4 focused tests, Ruff, and mypy passed, including exact batch/stream equality and future poisoning. | D-0018 |
| 2026-10-21 01:46 UTC | Causal extensions | Added sweep/reclaim, ATR-filtered three-bar gaps/fills, order-block proxy, HTF availability, event proximity, exact-time basis z-score, gated macro fields, historical book nulls, and transparent live-book calculations. | `src/tb/features/engine.py`, `src/tb/features/context.py`, focused tests | 11 focused tests, Ruff, and mypy passed. Subjective patterns are operational labels only. | D-0018 |
| 2026-10-21 01:53 UTC | Gold build | Added approved-asset/timeframe partitioning, feature-version manifests, completed-bar HTF joins, PowerShell runner, three-month equality coverage, and real-sample resume. | `.\scripts\build-gold-features.ps1`, `src/tb/features/pipeline.py` | 168 files / 51,940 rows / 8.1 MB; immediate rerun skipped all 168 partitions. | D-0018 |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 01:49 UTC | First real Gold build could not join timestamps. | Python record construction inferred microseconds while Silver stores nanoseconds. | Cast calculated timestamps back to the exact input dtype before the one-to-one join. | Existing batch integration now runs against both inferred microseconds and real nanosecond Silver. |
| 2026-10-21 01:52 UTC | First HTF rebuild found null/integer schema drift across prior Gold files. | A previously all-null HTF column inferred `Null`, and joining a prepared input duplicated the field. | Cast the authoritative engine output to nullable Int64, drop the staging copy before joining, and use relaxed concatenation while replacing v1 files. | Completed-bar HTF timing integration test remains green. |
