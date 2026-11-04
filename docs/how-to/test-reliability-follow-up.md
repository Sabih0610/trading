# Run the Wave 1 reliability follow-up checks

Use a credential-free checkout with no private .env. These tests use only fictional
owned paper inputs and datetime values. They never start a provider or external
order path. Run commands from the checkout root.

```powershell
uv sync --locked
uv run --locked pytest -q 'tests/integration/test_paper_validation.py' 'tests/unit/test_timeutil.py' 'tests/property/test_risk_guards.py'
```

The process-death test has four cases: entry and exit, each before and after commit.
Its child writes a readiness marker after opening/replaying the owned store, then
waits for the parent acknowledgement. The original fault hook still calls os._exit(71),
without Python cleanup. Startup has a 120s readiness bound, execution has 60s, and
cleanup communication has 10s. Timeout, early exit or a wrong exit code fails.

The datetime property warms both conversions in a module fixture and retains a
finite 2s example deadline. Its generated range and exact round-trip assertion stay
unchanged. Do not add skips, xfails, retries or wider input tolerances to hide failure.

The weekend-risk property also warms its actual registry/refusal path in a module
fixture. It keeps the default200ms deadline and reloads policy in every example;
there is no shared asset or policy cache between generated cases.

After the coordinated full-gate slot is available, use a clean credential-free checkout:

```powershell
pwsh -NoProfile -File './scripts/check-offline.ps1'
```

Keep one heavy suite active at a time. Record the candidate SHA and full result in
[the phase report](../../reports/phases/P11j-reliability.md). If readiness fails, inspect
the captured child error and the temporary owned test directory; no private credentials
or provider data are needed. A passing focused run does not replace the full gate.
