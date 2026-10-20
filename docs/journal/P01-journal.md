# P01 journal — Asset registry, Shariah gate, and risk configuration

P01 is encoding the non-negotiable project rules as versioned, validated configuration and deterministic guard functions. All work remains offline and key-free.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-20 22:45 UTC | Context | Read P01, the completed P00 report, current state, and review blockers. | `prompts/P01-registry-and-rules.md`, `reports/phases/P00.md` | P00 complete; no open review blockers; P01 started. | — |
| 2026-10-20 22:46 UTC | Research | Reviewed official Pydantic v2 model/validator/schema guidance and Binance spot `exchangeInfo`/filter contracts. | `docs/research/P01-research.md` | Strict versioned models, Decimal boundaries, nullable exchange metadata, and code-owned risk ceilings selected. | D-0006–D-0008 |
| 2026-10-20 22:48 UTC | Build | Added versioned asset/risk YAML, strict typed models, cross-policy validation, and pure risk guards. | `config/*.yaml`, `src/tb/risk/*.py` | Four approved spot assets, nine data-only instruments, immutable ceilings, and fail-closed checks implemented. | ADR-0001 |
| 2026-10-20 22:49 UTC | Test | Added unit, property, and hostile scenario tests for configuration and every guard. | `tests/unit`, `tests/property`, `tests/scenario` | Initial functional suite passed: 44 tests; lint found four style issues. | — |
| 2026-10-20 22:50 UTC | Harden | Expanded every-guard property coverage and forbidden source patterns to the complete policy list. | `tests/property/test_risk_guards.py`, `tests/scenario/test_forbidden_endpoints.py` | 48 tests passed; runtime source contained no prohibited product or unowned-sale paths. | — |
| 2026-10-20 22:51 UTC | Docs | Added the deterministic-authority ADR and operator guide; refreshed phase/living documentation. | `docs/adr/0001-*`, `docs/how-to/risk-policy.md` | P01 is resumable and ready for its final quality gate. | — |
| 2026-10-20 22:53 UTC | Verify | Ran Ruff, format, strict mypy, 48 offline tests, pre-commit, JSON validation, and hostile forbidden/final-test scans. | Commands in `reports/phases/P01.md` | All checks passed after exposing the WinGet uv directory to pre-commit. | — |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-20 22:49 UTC | Ruff reported one unused import, three ambiguous regex match strings, and four format drifts. | New test files had not received the repository formatter; regex intent was not explicit. | Removed the import, made regex strings raw/escaped, and ran Ruff format. | Existing suite remained green. |
| 2026-10-20 22:50 UTC | The first hostile scan omitted four prohibited families and not every guard had a distinct property test. | Initial implementation covered prompt scenarios but not the strictest interpretation of the project-wide acceptance language. | Added earn/loan/staking/leverage patterns plus properties for tradability, spot, accepted inventory sales, and trade counts. | `test_forbidden_endpoints.py`, `test_risk_guards.py` |
| 2026-10-20 22:53 UTC | Pre-commit hooks reported `Executable uv not found` although direct uv checks passed. | WinGet updated the persistent user PATH after this long-running PowerShell process started; hook child processes inherited the old PATH. | Prepended uv’s resolved install directory to this process PATH and reran all hooks. | All four hooks passed; no source change required. |
