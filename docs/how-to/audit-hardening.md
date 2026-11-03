# Audit hardening and test diagnostics

J1 Wave 1 hardens research mechanics without widening risk or changing engine fill-price/priority rules or labels.
Noncanonical entry symbols reject, quantity capacity arithmetic rounds down and
all chart modes refuse 2025+ observations. Default commands need no provider keys.

## Check the boundaries

From a credential-free checkout:

```powershell
uv sync --locked
uv run --locked pytest -q './tests/unit/test_audit_minors_wave1.py' './tests/unit/test_skill_installer_pins.py' './tests/review/full_audit/test_risk_rules.py'
pwsh -NoProfile -File './scripts/check-offline.ps1'
```

The two owner-named native-query properties warm outside their timed examples and
retain every assertion/example count. Their local 2s deadline covers the measured
1.108s concurrent Windows outlier; all other Hypothesis deadlines stay unchanged.
A test exceeding 600s causes pytest to dump all thread stacks, then continue. This
is diagnostic evidence, not a test skip/pass or abort. Preserve the log and identify
the blocked operation. Never rerun silently to hide a semantic failure.

Direct test subprocess calls have explicit 30s/120s bounds. The owned OAuth test
uses 5s socket operations, a 10s/64KiB response bound, and a 5s joined-thread assertion;
the source callback listener already has a 300s/20-request bound. Writer leases
are OS-held nonblocking locks; SQLite connections use bounded library waits.

## Optional configuration logs

```powershell
uv run --locked tb doctor
```

Startup names/reasons for missing optional integrations appear on stderr and in
logs/trading-bot.jsonl once per process; no values, secret lengths or private paths
are recorded. JSON-producing CLIs retain clean stdout. Initializing logging does
not open a private `.env`: when one exists, actual feature availability is logged only
when the component loads its settings. A configured key never authorizes a provider
or order by itself; existing consent/rights/runtime gates remain mandatory.

## Review skill sources

```powershell
pwsh -NoProfile -File './scripts/install-skills.ps1' -ListOnly
```

This fetches only the full reviewed commits recorded in docs/skills.md, checks a
detached identity and refuses modified cache checkouts. Review retained files before
using the non-list installation command. The fixture test replaces Git completely;
it performs no network fetch and executes no third-party content.

S-1 removed 122 ignored tracked paths from the index only: 30 kit and 92 legacy quality
metadata paths. Existing local files were retained without opening their contents;
new clean checkouts omit them. No history rewrite was made.
