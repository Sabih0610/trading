# P09 — Decision ledger and AI arena (offline-first, APIs added later)

Follow `prompts/_PROTOCOL.md`.

## Goal
An append-only decision ledger and a model-agnostic "arena" where multiple AI models
independently review setups, cross-review each other, propose hypotheses, and get scored — with
caching and hard budget caps. Works fully with mock and local models; paid APIs plug in later.

## Research first
- OpenAI-compatible client patterns (xAI, DeepSeek, Qwen, OpenAI share it); Anthropic SDK; Ollama
  local API. Structured/JSON-schema outputs and validation; retries; timeouts.
- Provider prompt caching and batch APIs (cost reduction); response caching keyed by content hash.
- Local models that fit a 4 GB GTX 1650 Ti (≤~4B params, 4-bit) and realistic tokens/s.
- Scoring and combining forecasters: Brier score, log loss, multiplicative-weights / Hedge
  ensembles, error-correlation (herding) measurement.
- Interface for Jev (decision model) — design the adapter only; implementation comes later.

## Build
1. `src/tb/ledger/`: SQLite (WAL mode) append-only tables: decisions, model_calls, outcomes,
   hypotheses, interventions; every row has versions (model, prompt, question-set, features) and
   hashes; outcomes back-filled when a setup resolves. Nightly export to Parquet (gold layer).
2. `src/tb/agents/providers/`: `MockProvider`, `OllamaProvider`, `OpenAICompatibleProvider`
   (base_url + key from `.env`), `AnthropicProvider`, `JevProvider` (stub). Missing key ⇒ disabled.
3. Snapshot masking: features only — no symbol names, dates or raw prices.
4. Arena rounds: (1) independent JSON answers {decision: take|skip, confidence, reason_code,
   key_risk}; (2) one anonymized cross-review round; (3) hypothesis proposals in a fixed schema →
   `hypothesis_queue` → the backtester tests them automatically; results stored per model.
5. Cache: diskcache/SQLite keyed by hash(snapshot, questions, model, version) with TTLs.
6. Budget: `config/ai_budget.yaml` (monthly + daily caps per provider, default total $20/month);
   token accounting per call; when a cap is reached the provider is skipped and logged.
7. Scoring: per-model paper portfolio, Brier, calibration bins, veto value (shadow outcomes),
   hypothesis hit rate, cost per useful decision; ensemble weights via multiplicative weights.
8. Hard rule in code: arena outputs can only produce veto/size-reduction signals.

## Scenarios to self-test
Malformed JSON from a model · timeout · provider down · budget cap hit mid-day · cache hit/miss ·
identical answers from all models (herding flag) · an answer trying to "increase size" (rejected).

## Acceptance
Runs end-to-end with MockProvider and (if installed) Ollama; zero paid calls required; report written.
