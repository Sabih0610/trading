# P05 journal — feature engine

P05 is building one deterministic, causal feature implementation shared by batch research and
bar-by-bar paper/live evaluation. Every feature will declare its inputs, warmup, confirmation lag,
timeframe, and version; unavailable licensed or historical inputs remain explicitly null.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 01:39 UTC | Context | Read P05, P04 report/handoff/state, the mandatory project rules, and the quant-analysis skill. | `prompts/P05-feature-engine.md`, `.agents/skills/` | P05 started from the tagged P04 checkpoint. Quant guidance is limited to deterministic spot-safe feature methodology. | — |
| 2026-10-21 01:40 UTC | Research | Searched current Polars, Binance Spot, TradingView pivot, and online-algorithm references for causal rolling windows, confirmed pivots, local order books, and batch/stream parity. | `docs/research/P05-research.md` | Research in progress; subjective structure terms will receive explicit project definitions and confirmation delays. | — |
| 2026-10-21 01:43 UTC | Shared core | Added versioned feature metadata and one streaming state for ATR, realized volatility, EMAs/slopes, confirmed pivots, structure breaks, VWAP, and session levels; batch replays it. | `src/tb/features/engine.py`, `tests/unit/test_feature_engine.py` | 4 focused tests, Ruff, and mypy passed, including exact batch/stream equality and future poisoning. | D-0018 |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
