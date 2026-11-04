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
volume/VWAP,54trials, G-2 registry full quoted spread halved per fill, asset's stricter risk overrides,
training>=20rule, development-only verdict and no2024boundary.

After gates, push with skip-ci/no tags, open PR and create empty
reports/reviews/queue/P11g-prereg.ready. The review on main3c4caf7 explicitly APPROVES conditional on verbatim G-1/G-2.
Those amendments require no further pre-registration review. Verify their exact
text and journal SHA, then test/freeze complete Part B source before genuine input. Poll main
while other tracks work. Never run genuine inputs or create a frozen-parameter
file from observations before that approval. Shared living entries stay in phase report.

A must survive both default touch and strict trade-through LIMIT paths, both
orderings and all registered costs with unchanged training selections. This flag
is research-only; the engine default changes only in separately gated J2.
