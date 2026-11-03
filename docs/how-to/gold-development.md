# Gold development pre-registration and review

Part A contains owned fixtures, a research-only proxy boundary, ORB strategy and
fixed54-cell catalogue. No genuine reader/run CLI is supplied before review.
XAU stays data-only; paper, simulation, Testnet and orders are refused.

From this credential-free checkout, run fixtures only:

```powershell
uv run --locked pytest -q './tests/unit/test_gold_stage3.py' './tests/property/test_session_orb.py' './tests/unit/test_gold_preregistration.py'
pwsh -NoProfile -File './scripts/check-offline.ps1'
Get-FileHash -LiteralPath './reports/stage3/P11g-preregistration.md' -Algorithm SHA256
```

Check the journal SHA against exact registration bytes. Review the low stop,
London08:00/NY09:30 anchors and independent DST,5%coverage windows, absent real
volume/VWAP,54trials, per-side XAUT cost floor, asset's stricter risk overrides,
training>=20rule, development-only verdict and no2024boundary.

After gates, push with skip-ci/no tags, open PR and create empty
reports/reviews/queue/P11g-prereg.ready. G stops until
reports/reviews/P11g-prereg-review.md on main explicitly says APPROVED. Poll main
while other tracks work. Never run genuine inputs or create a frozen-parameter
file from observations before that approval. Shared living entries stay in phase report.
