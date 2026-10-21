# P09 research — append-only ledger and constrained AI arena

Research date: 2026-10-22 (Asia/Karachi). The arena is post-proposal decision support: it cannot
create a setup, enlarge a risk-approved size, change a stop, or bypass deterministic risk. The
complete acceptance path must work offline with zero credentials and zero paid calls.

## Questions and decisions

| Topic | Evidence / alternatives | Decision |
|---|---|---|
| Evidence store | SQLite WAL lets readers continue while a writer appends, but WAL is a same-host design. SQLite row triggers can abort update/delete operations. | Use one local SQLite WAL database. Every evidence table has permanent update/delete rejection triggers. A resolution is a new `outcomes` row, never an update to a decision. Export nightly snapshots to checksummed Gold Parquet. |
| Provider boundary | Provider SDKs offer conveniences but add large, rapidly changing dependencies. OpenAI-compatible, Anthropic, and Ollama endpoints all accept structured JSON forms. | Use the existing pinned `httpx` boundary, bounded retries/timeouts, native JSON Schema where supported, and mandatory local Pydantic validation. Missing keys disable adapters. Jev remains a non-calling stub. |
| Structured responses | Constrained decoding greatly reduces syntax/schema errors, but refusals, incomplete results, proxy incompatibility, and transport failures still exist. | Treat provider schema enforcement as a first layer only. Reject any response that fails the local frozen schema. Extra fields, invalid enums, NaN/inf, and size multipliers above 1 fail closed and have no arena effect. |
| Snapshot privacy | Symbols, exact timestamps, dates, and raw prices are unnecessary identifiers for a feature review and could leak instrument/time identity. | Accept only a `MaskedSnapshot`; tokenize field names and reject symbol/ticker/date/time/UTC/open/high/low/close/bid/ask/price/raw tokens before hashing or calling a provider. |
| Cache | Provider prompt caches reduce repeated prefix cost but differ by vendor and TTL. An application cache is provider-neutral. | Keep a separate operational SQLite TTL cache keyed by the canonical snapshot/questions/schema/provider/model/versions. Log cache hits to the immutable ledger. Never treat cache rows as audit evidence. |
| Budget | Providers usually return tokens, not trustworthy dollar cost. A zero price would silently bypass a money cap. | Paid providers are policy-disabled by default even if a key exists. Enabling one requires explicit nonzero input/output prices and caps in human-edited YAML. Reserve `max_call_usd` before calls; account configured/returned actual cost afterward, including cost-exceeded calls. Global default remains $20/month. |
| Local model | The host has 4 GB VRAM. Ollama lists Qwen2.5 3B at about 1.9 GB and Gemma 3 4B Q4_K_M at about 3.4 GB, but runtime speed depends on context/offload/driver. | Enforce declared `<=4B` and exactly 4-bit quantization. Do not promise tokens/second without a host benchmark. Do not run local inference during model training. |
| Arena authority | Majority voting can amplify correlated errors and create new trades. Independent review plus peer review improves evidence but not authority. | Run independent answers, one anonymized cross-review, and fixed-schema research hypotheses. Final effect is the minimum validated multiplier in `[0,1]`; skip/veto maps to zero. Invalid/unavailable opinions are optional and cannot create a veto by themselves. |
| Scoring | Brier and log loss are proper probability scores. Multiplicative weights reduce weight after cumulative loss. Identical answers can reveal herding. | Store per-model forecasts/outcomes; provide Brier, clipped log loss, reliability bins, Hedge weights, identical-answer flag, and pairwise error correlation. Treat small samples and null correlations honestly. |
| Batch/caching APIs | Vendor batch and prompt caches can lower costs, but async batches complicate pre-trade timing and vendor cache semantics are not audit storage. | Do not use remote batches in the synchronous pre-trade path. Consider them later only for hypothesis research after the same budget and ledger boundaries. |

## Sources

- [SQLite WAL](https://www.sqlite.org/wal.html) — concurrency, persistence, and same-host limitation; accessed 2026-10-22.
- [SQLite CREATE TRIGGER / RAISE](https://www.sqlite.org/lang_createtrigger.html) — aborting update/delete operations; accessed 2026-10-22.
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) — strict JSON Schema and typed SDK helpers; accessed 2026-10-22.
- [OpenAI Python API reference](https://developers.openai.com/api/reference/python) — timeout/retry configuration and typed API failures; accessed 2026-10-22.
- [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — constrained JSON and strict tool schemas; accessed 2026-10-22.
- [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — automatic/explicit breakpoints and 5-minute/1-hour TTLs; accessed 2026-10-22.
- [Anthropic message batches](https://platform.claude.com/docs/en/api/messages/batches) — asynchronous create/poll/result workflow; accessed 2026-10-22.
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) and [generate API](https://docs.ollama.com/api/generate) — JSON Schema input and token/cache counters; accessed 2026-10-22.
- [Ollama Qwen2.5 library](https://ollama.com/library/qwen2.5) and [Gemma 3 4B Q4_K_M](https://ollama.com/library/gemma3%3A4b-it-q4_K_M) — small-model parameter/file-size evidence; accessed 2026-10-22.
- [Vovk and Zhdanov, Prediction with Expert Advice for the Brier Game](https://jmlr.org/papers/volume10/vovk09a/vovk09a.pdf) — probability loss and loss-weighted experts; accessed 2026-10-22.

## Risks and unknowns

- No paid provider is enabled or called in P09. Prices and model identifiers change; a human must
  set current token prices, caps, and `enabled: true` before any paid trial.
- Native structured-output dialects can change. Local validation and adapter fixture tests remain
  authoritative even when a provider claims schema enforcement.
- The arena has no demonstrated trading value. P07/P08 lack eligible XAUT evidence, so provider
  forecasts, veto value, hypothesis hit rate, and cost per useful decision are NOT EVALUABLE.
- SQLite WAL must stay on one host/local filesystem. Network-share deployment needs a different
  storage decision, not a relaxed SQLite setting.
