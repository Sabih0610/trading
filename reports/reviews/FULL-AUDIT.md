# Full project audit — Claude review

| Field | Value |
|---|---|
| Date | 2026-11-01 |
| Reviewer | Claude (Claude Code, reviewer/stress-tester role per `CLAUDE.md`) |
| Scope | Whole repository at `main` `aa65e85` (P00–P11c.0) |
| Method | `prompts/REVIEW_CLAUDE.md`: rules audit, correctness reading, independent tests, gates rerun |
| Independent tests | `tests/review/full_audit/` — 92 passed, 20 strict xfail (each xfail = one verified finding) |
| Verdict | **APPROVED WITH FIXES** — no blockers; 5 major and 16 minor findings |

## 1. Summary

No blocker was found. The core safety rules hold in code and under adversarial tests:

- **Long-only and spot-only:** no short-sell path, no negative holdings, no leverage, no futures/margin/earn/staking/withdraw endpoints, no exchange SDK. No order path exists for any venue (`src/tb/execution/` is empty; cTrader and MT5 boundaries are read-only allowlists).
- **Risk authority:** hard ceilings compiled in `src/tb/risk/config.py:15-18`; YAML and per-asset overrides can only tighten. Sizing never exceeds risk budget, cash or 1.0× exposure (property-tested over all four tradable assets). Daily and peak-drawdown halts latch correctly.
- **AI cannot enlarge trades:** arena multipliers are bounded to [0, 1]; even forged values (5, inf, NaN, −1) cannot raise size.
- **No lookahead in features:** truncating or perturbing future bars never changes past features; pivots confirm 3 bars late; HTF joins use only closed bars; no forward fill across gaps.
- **Final-test lock holds:** 2025+ data is refused by absolute UTC instant across the runner, importer, labels and walk-forward defaults, including timezone edge cases.
- **Secrets:** no secrets in code or in any of the 66 commits; keys travel in headers, never URLs; providers disable cleanly with zero keys; dashboard binds to 127.0.0.1 and has no write controls.

The weaknesses are in **backtest fill realism** (one optimistic same-bar rule), **the forbidden-endpoint guard** (easy to evade), **MLflow telemetry** (outbound network in a default test), **the local `.env` permissions**, and documentation drift.

## 2. Quality gates (rerun in this checkout)

| Gate | Result |
|---|---|
| `pytest` (default, `-m 'not live'`) | 1,078 passed, **6 failed**, 3 deselected (8 m 52 s) |
| `ruff check src tests` | Clean (after fixing one lint error in the new review tests) |
| `mypy src` (strict) | Clean — 177 source files |
| Review tests `tests/review/` | 92 passed, 20 xfailed (strict) |

**The 6 failures are environmental, not code defects.** This folder is the owner's original checkout and contains a `.env`:

- 5 × `tests/unit/test_offline_ci.py::test_windows_entrypoint_propagates_each_quality_failure[*]` — `scripts/check-offline.ps1:7` deliberately throws "Run offline validation in a separate checkout without a private .env" before calling the fake `uv`, so the trace file is never written.
- 1 × `tests/integration/test_ctrader_onboarding_offline.py::test_default_cli_missing_keys_is_inert_and_has_no_sensitive_fields` — the CLI correctly refuses with `private_storage_invalid` because the real `.env` has unsafe ACLs (finding S-5).

Codex's reported 1,084 passes come from a clean, credential-free checkout. See finding T-1.

## 3. Findings

Severity: **blocker** = must fix before any further phase; **major** = fix before relying on results or before P11c.1; **minor** = fix when convenient.

### Major

| ID | Area | File:line | Description | Evidence | Suggested fix (for Codex) |
|---|---|---|---|---|---|
| D-1 | Backtest realism | `src/tb/backtest/engine.py:357-361, 423` | A limit entry filled intrabar (`low <= limit`) immediately runs `process_exit(bar)` on the same bar, so a bar whose high reaches the target books a same-bar TARGET win. OHLC cannot show the high came after the fill; this is optimistic and inflates win rate for limit-entry strategies (Strategy A uses FVG limit entries). | `test_data_leakage.py::test_limit_fill_cannot_also_take_profit_in_the_same_bar` — O100/H110/L95, limit 96, target 105 → TARGET exit, P&L +69.6 | On the fill bar of an intrabar limit fill, evaluate only the stop; defer target checks to the next bar. Add a regression test. |
| S-2 | Forbidden-endpoint guard | `tests/scenario/test_forbidden_endpoints.py:9-20` | The guard misses `fapi`/`dapi`/`sapi` hosts, `withdraw`, camelCase `simpleEarn`, split strings, `import ccxt`/`binance`, and order endpoints (`/api/v3/order`); scans only `*.py`. `src/tb/agents/providers/http.py:59` already builds `"opt" + "ions"` to step around it. | 6 strict xfails in `test_security.py` plant each pattern and show the existing test passes | Add those patterns case-insensitively; scan `.py`, `.yaml`, `.ps1`; add an order-endpoint list and an AST import check for exchange SDKs; replace the `"opt"+"ions"` workaround with an explicit, reviewed allowlist entry. |
| S-6 | Network / privacy | `src/tb/ml/tracking.py` | MLflow telemetry is never disabled. The default (non-live) test `tests/unit/test_ml_tracking.py::test_local_run_records_params_metrics_tags_and_artifact` performs a DNS lookup of `config.mlflow-telemetry.io`; the failure is swallowed so the test passes. Breaks "no network in default tests" and leaks usage telemetry from real runs. | Socket audit hook during the default suite; `test_security.py::test_mlflow_telemetry_is_disabled_by_project_code` (xfail) | Set `MLFLOW_DISABLE_TELEMETRY=true` and `DO_NOT_TRACK=1` before importing mlflow in `tracking.py`, and in `tests/conftest.py`; add a socket-denying fixture to default tests. |
| S-5 | Secrets (environment) | `E:\trading bot\.env` | `icacls` shows inherited `Authenticated Users:(M)` and `Users:(RX)` — any local account can read or modify the secrets file. The repository's own `PrivateEnv.require_private` rejects it. | `icacls .env`; `test_security.py` S-5 xfail (skips when no `.env`) | **Owner action:** remove inheritance and grant only your user and SYSTEM, e.g. `icacls .env /inheritance:r /grant:r "%USERNAME%:(F)" "SYSTEM:(F)"`. Codex: make `scripts/setup.ps1` apply this ACL when it creates `.env`. |
| R-1 | Shariah/risk rule | `src/tb/risk/guards.py:173`; `src/tb/risk/config.py:223,255` | "No XAUT weekend entries" is not enforced by its own flag. `allow_xaut_weekend_entries` is validated as false but never read; `check_session` reads only `asset.weekend_trading`, so setting `weekend_trading: true` for XAUTUSDT in `assets.yaml` enables Saturday XAUT entries. A human config edit, but it widens a rule AGENTS.md calls non-negotiable. | `test_risk_rules.py::test_xaut_weekend_rule_cannot_be_reenabled_via_asset_registry` (xfail) | Reject `weekend_trading: true` for any XAUT symbol in the `PolicyBundle` validator, and have `check_session` also consult `limits.allow_xaut_weekend_entries`. |

### Minor

| ID | Area | File:line | Description | Suggested fix |
|---|---|---|---|---|
| R-2 | Risk | `src/tb/backtest/engine.py:254-257` | The backtest circuit breaker uses global `bundle.risk.limits`, not `effective_risk_limits(asset, ...)`, so a tighter per-asset daily-loss override never triggers intraday liquidation (entries are still blocked). `paper/simulation.py:216` is correct. | Pass `effective_risk_limits(self.asset, ...)`. |
| R-3 | Risk | `src/tb/risk/manager.py:131` | Lowercase/padded symbol or blank market raises pydantic `ValidationError` instead of returning a `RiskDecision`. Fails closed, but callers get an exception, not a rejection code. | Normalise symbol; catch construction errors and return a rejection. |
| R-4 | Risk | `src/tb/risk/manager.py:104-109,187` | With `exchange_rules: null` (all shipped assets), quantity is unquantised 28-digit Decimal with half-even rounding — approved risk can exceed the budget by ~1e-29 and quantities are not exchange-executable. | Quantise `ROUND_DOWN` to a default step; populate `exchange_rules`. |
| D-2 | Backtest lookahead | `src/tb/backtest/engine.py:394` | Fill size is capped by `bar.volume × participation_rate` of the bar being filled at its open; that volume is only known at bar close. | Use the previous completed bar or a trailing median. |
| D-3 | Backtest realism | `src/tb/backtest/engine.py:357-359` | Limit buys fill on a touch (`low <= limit`) with no trade-through or queue model. | Require `low < limit` or a configurable trade-through/fill probability. |
| D-4 | ML labels | `src/tb/ml/labeling.py:113-117` | Triple-barrier LOSS booked at the stop even when the bar gapped through it; `LabelBar` has no `open`. Labels understate losses. | Add `open`; use `min(open, stop)`; consider net-of-cost returns. |
| D-5 | Features | `src/tb/silver/pipeline.py:281-282`, `src/tb/features/context.py:27-31` | Calendar `known_at = scheduled_utc`, so `minutes_to_high_impact_event` is always null before events — the feature is dead and the news-window logic has no lead time. Not a leak. | Set `known_at` to the schedule's first-seen/fetch time. |
| D-6 | Final-test lock | `src/tb/dashboard/readers.py:358-372` | Dashboard skips the 2025+ filter when a manifest self-declares `mode == "synthetic"`. Uncertain (code reading only). | Always apply the date filter, or require an unforgeable synthetic marker. |
| D-7 | Silver quality | `src/tb/silver/market.py:183-188, 266-271` | Gap counter resets at each partition, hiding cross-partition gaps; partial resampled bars reach Gold unfiltered (no leak — engine resets on gaps). | Seed gap from previous partition; flag/skip partial HTF bars in Gold. |
| S-1 | Repo hygiene | `.gitignore:23-24` | `trading-bot-dev-kit.zip` and 30 files under `trading-bot-dev-kit/` are tracked despite being ignored. Contents checked: no secrets. | `git rm --cached` them, or drop the ignore rule. |
| S-3 | Secrets in transit | `src/tb/agents/providers/http.py:41,101,172` | Default `httpx.Client()` has `trust_env=True`; proxy/.netrc env could route bearer-key requests through a proxy. All other adapters set `trust_env=False`. | `httpx.Client(trust_env=False, follow_redirects=False)`. |
| S-4 | Logging | `src/tb/core/logging.py:65-77,104` | `RedactingFilter` does not redact exception tracebacks; `configure_logging` is never called anywhere in `src`, so redaction is unused. | Redact formatted `exc_text`/`stack_info`; call `configure_logging(known_secrets=...)` at every entry point. |
| S-7 | Supply chain | `scripts/install-skills.ps1:26-37` | Third-party skill repos cloned at unpinned HEAD and copied into `.claude/skills`. | Pin each repo to a commit SHA. |
| S-9 | Ops | repo-wide | AGENTS.md §3 asks for a clear log line when a key is missing; features disable correctly but nothing is logged. | Log once per disabled feature at startup. |
| T-1 | Test hermeticity | `tests/unit/test_offline_ci.py`, `tests/integration/test_ctrader_onboarding_offline.py` | 6 default tests fail whenever the checkout contains a `.env` (by design of the scripts), so the suite cannot be green in the owner's working folder. | Skip with an explicit reason when `ROOT/.env` exists, or run these against a temporary copy of the repo. |
| T-2 | Test flakiness | `tests/unit/test_shadow_runtime.py::test_two_simultaneous_processes_cannot_own_shadow_writer`, `tests/integration/test_ctrader_onboarding_offline.py::test_default_cli_missing_keys_is_inert_and_has_no_sensitive_fields` | In a clean credential-free worktree, both failed once during a full 11-minute suite run (pre-commit hook) and passed when rerun alone — timing-dependent under load. | Widen process-start/lease timeouts or synchronise on an explicit readiness signal instead of wall-clock waits. |

### Informational / policy questions (no change requested by the reviewer)

- **I-1 Shariah direction (owner + scholar).** Since P09.5 the primary research target is XAUUSD/EURUSD contract simulation. The code keeps them `data_only` and no order path exists, so nothing violates AGENTS.md today. The project record (§3.1) rejected CFDs; a scholar ruling is needed before any broker-execution phase.
- **I-2 Weekend definition.** "Weekend" is Saturday/Sunday UTC, so XAUT entries are allowed Friday 21:00–24:00 UTC after spot gold closes. Consider aligning with the gold market close.
- **I-3 Offline paper stop fills** fill at the next quote's bid, which can exit above the stop on a recovery — slightly optimistic.
- **I-4 cTrader OAuth** has no `state`/PKCE; compensated by a 256-bit one-use loopback path, 127.0.0.1 bind, 300 s / 20-request limits. Acceptable.
- **I-5 Documentation drift.** `AGENTS.md` §2 still states 1% risk / 3% daily loss while §1 and `config/risk.yaml` use 0.5% / 2% / 5% (code ceilings are 1% / 3%; config is tighter — both are consistent with "config may only tighten", but §2 should say so). `README.md` still says to clone `codex/p11c-0-research-mvp` "pending review", but it is merged into `main`.
- **I-6 Review backlog.** Every phase's independent review is queued or deferred. This audit covers the whole codebase but is not a substitute for the P11c.0 and RC-remediation reviews the handoff asks for.

## 4. Backtest and data realism checklist

| Check | Result |
|---|---|
| Lookahead in features | Pass (property tests) |
| Final-test lock (2025+) | Pass, incl. timezone edges; D-6 open question |
| Purged / embargoed CV | Pass (property test, k-fold / expanding / combinatorial) |
| Market fills at next bar open | Pass |
| Stop vs target in same bar | Pass (stop first) — **except limit-fill bar (D-1)** |
| Gap through stop | Pass (exit at open) in backtester; D-4 in ML labels |
| Costs both sides, match `assets.yaml` | Pass (10 bps fee + half-spread + slippage; stress ≥ 1) |
| Volume participation | D-2 (uses fill-bar volume) |
| Survivorship | N/A — fixed four-asset universe; XAUT history correctly reported as insufficient |
| Real-data results | **None exist** — genuine evaluation is blocked pending a licensed dataset, so no strategy edge has been demonstrated |

## 5. Independent tests added

All under `tests/review/full_audit/` (new; no existing test or source file was modified):

| File | Focus | Result |
|---|---|---|
| `test_risk_rules.py` | Long-only, sizing, halts, overrides, weekend, AI multiplier, backtest invariants (hypothesis) | 48 passed, 4 xfail (R-1…R-4) |
| `test_data_leakage.py` | Feature causality, Silver, final-test lock, purged CV, fills/costs | 18 passed, 5 xfail (D-1…D-5) |
| `test_security.py` | Forbidden patterns, secrets, redaction, proxies, telemetry, hygiene | 26 passed, 11 xfail (S-1…S-6) |

Each xfail is `strict=True`: when Codex fixes a finding, the matching test will XPASS and fail the suite, signalling that the `xfail` marker should be removed so the test becomes a permanent regression guard.

## 6. Required actions

**Owner (now):** fix `.env` ACLs (S-5); decide on I-1 with your scholar before any broker phase.

**Codex (before P11c.1):** D-1, S-2, S-6, R-1, then T-1 so the suite is green in the owner's checkout. Remove each matching `xfail` marker when fixed. Never weaken an existing test or risk rule to do so.

**Codex (when convenient):** remaining minors; align `AGENTS.md` §2 and `README.md` (I-5).
