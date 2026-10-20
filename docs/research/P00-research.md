# P00 research — project bootstrap and Windows tooling

This research selects a reproducible Python 3.12 project layout, strict quality tools, safe configuration loading, structured secret-redacting logs, and DST-correct time helpers. Sources were checked on 2026-10-20 UTC, with official documentation preferred.

## Questions asked

- How should a uv-managed Windows application be laid out and locked?
- Which Ruff, mypy, pytest, Hypothesis, and pre-commit defaults produce a strict but maintainable baseline?
- How should optional `.env` keys and malformed or unrelated lines behave?
- How can structured logs remain useful without leaking key-like values?
- How should London and New York sessions handle DST transitions?
- How should PowerShell setup behave when execution policy or optional tools differ?

## Options compared

| Topic | Options | Decision | Why |
|---|---|---|---|
| Package layout | Flat package; scripts only; installable `src/` package | Installable `src/tb` application | uv creates package applications with build metadata, while pytest recommends src layout/importlib mode to avoid importing the wrong checkout. |
| Dependency reproducibility | Requirements file; broad ranges; uv project + lock | uv project with exact direct dependency pins and committed `uv.lock` | uv lockfiles are cross-platform and `uv run` automatically keeps the environment synchronized. |
| Type/lint config | Tool-specific files; centralized `pyproject.toml` | Centralized strict config in `pyproject.toml` | Ruff and mypy discover project settings there; one root config is easier to audit. |
| Settings | Hand-written dotenv parsing; Pydantic Settings | Pydantic Settings, optional `SecretStr`, `extra="ignore"` | Typed optional keys switch features off cleanly while unrelated dotenv values do not break startup. YAML is separately validated with Pydantic models. |
| Logging | structlog; stdlib; stdlib + Rich console | stdlib JSON file formatter + Rich console handler, both behind redaction | Standard logging integrates dependencies and Python 3.12 handler filters can sanitize records before formatting. |
| Time zones | Fixed offsets; pytz; stdlib `zoneinfo` + `tzdata` | `zoneinfo` with UTC as storage boundary | IANA zones handle DST and `fold`; `tzdata` supplies zone data on Windows when the OS has none. |
| PowerShell policy | Change machine policy; process bypass; detect and explain | Never mutate policy; report effective policy and document a process-scoped invocation if needed | Group Policy can override local settings, and persistent policy changes are outside project setup scope. |
| Property testing | Disable health checks; defaults; deterministic custom profile | Defaults locally, deterministic CI profile only when CI sets it | Hypothesis warns against blanket health-check suppression; its defaults already balance speed and edge coverage. |

## Decision and implementation notes

1. `pyproject.toml` will declare Python 3.12, the `tb` CLI, strict mypy, Ruff, pytest importlib mode, and a `live` marker that is skipped only by test selection—not by hidden network behavior.
2. `.env` is optional. Every integration secret is `SecretStr | None`; the feature report exposes booleans only. Unknown dotenv entries are ignored, while known fields still receive type validation.
3. JSON logs go to `logs/trading-bot.jsonl`. Redaction is applied on both handlers and covers known secret values, credential field names, bearer tokens, and common provider-token shapes.
4. Time helpers reject naive datetimes, store UTC nanoseconds, and derive local session boundaries by converting aware local values through IANA zones.
5. Setup checks tools and versions, uses uv-managed Python 3.12, never overwrites `.env`, and does not change execution policy.

## Sources

Accessed 2026-10-20 UTC.

- [uv: creating projects](https://docs.astral.sh/uv/concepts/projects/init/) — packaged applications use a build system and `src/` layout.
- [uv: locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/) — `uv.lock`, automatic sync, and locked/frozen behavior.
- [uv: installation](https://docs.astral.sh/uv/getting-started/installation/) — official Windows installer and WinGet methods.
- [Ruff configuration](https://docs.astral.sh/ruff/configuration/) and [formatter](https://docs.astral.sh/ruff/formatter/) — centralized configuration and check-mode formatting.
- [mypy configuration](https://mypy.readthedocs.io/en/stable/config_file.html) — `pyproject.toml` discovery and unused-config warnings.
- [pytest good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html) — external tests, src layout, and importlib mode.
- [Hypothesis settings](https://hypothesis.readthedocs.io/en/latest/settings.html) — default property-test behavior and health-check guidance.
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — dotenv loading, unknown variables, secret types, and source priority.
- [Python 3.12 logging](https://docs.python.org/3.12/library/logging.html) — filters, handlers, and replacement `LogRecord` support.
- [Python `zoneinfo`](https://docs.python.org/3.11/library/zoneinfo.html) — IANA data fallback, DST arithmetic, and `fold` handling.
- [PowerShell execution policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies) — scope/precedence and Group Policy behavior.
- [pre-commit](https://pre-commit.com/) — installation and running new hooks over all files.

## Risks and unknowns

- WinGet provided uv 0.13.3 while 0.13.4 was already available upstream; the lock/build remains valid, and the setup script accepts compatible current uv versions rather than depending on patch-level behavior.
- Windows time-zone support may depend on the PyPI `tzdata` fallback, so it is a direct runtime dependency and DST transitions receive explicit tests.
- Heuristic redaction cannot mathematically identify every secret; known configured secret values are always registered, and structured field-name redaction provides a second layer.
- Third-party skills are untrusted text until reviewed. The installer copies only allowlisted skill directories and no copied script is executed during review.
