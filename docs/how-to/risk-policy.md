# Risk policy and asset registry

P01 provides the configuration and deterministic guard layer that later trading code must call. It works offline, uses no credentials, and fails closed when an asset is not approved, an order is not spot/inventory-backed, or a risk boundary is crossed.

## Files and inputs

- `config/assets.yaml` is the versioned asset registry. Only `role: tradable` plus `shariah_status: approved` can pass the tradability guard.
- `config/risk.yaml` holds operator-visible limits. Values may equal or tighten the compiled ceilings; they cannot widen them.
- `src/tb/risk/config.py` validates both files and computes effective per-asset limits.
- `src/tb/risk/guards.py` contains pure checks for asset eligibility, spot-only orders, owned inventory, exposure, loss, trade count, trade risk, and sessions.

All percentages are percentage points: `1` means 1%, not 100%. Monetary and quantity inputs use `Decimal`.

## Validate the policy

From the repository root:

```powershell
uv run pytest -q tests/unit/test_risk_config.py tests/unit/test_risk_guards.py tests/property/test_risk_guards.py tests/scenario/test_forbidden_endpoints.py
```

Load and inspect only non-secret policy values:

```powershell
uv run python -c "from tb.risk.config import load_policy_bundle; p=load_policy_bundle(); print([a.symbol for a in p.registry.assets if a.role.value == 'tradable']); print(p.risk.limits)"
```

Expected tradable symbols are `XAUTUSDT`, `BTCUSDT`, `ETHUSDT`, and `SOLUSDT`.

## Safely tighten a limit

Edit `config/risk.yaml` or an asset's `risk_overrides`, then run validation. Only a human may edit
policy. Per-asset values cannot exceed the compiled ceiling or active global value. P09.5 defaults
are 0.5% planned all-in risk, 2% daily net-equity loss, 5% peak drawdown and one open position.
XAUT tightens planned risk to 0.25% and two entries per day. The legacy compiled upper bounds of
1% trade risk / 3% daily loss remain absolute configuration ceilings, not the active defaults.

The shared account circuit observes liquidation equity including fees and unrealized P&L; daily
halts latch until UTC rollover and peak halts persist. Entry and actual-fill sizing include costs.
Gold/FX use a separate fully funded local accounting boundary with explicit timestamped contract
facts; this does not relax `assert_tradable` or authorize any external order. See
[the simulation guide](alignment-simulation.md).

Never treat null `exchange_rules` as an absent exchange restriction. It means that public spot metadata has not yet been synchronized; later execution code must fail closed until required filters are present.

## Troubleshooting

- `extra_forbidden`: remove the unknown/misspelled YAML field; do not add a permissive fallback.
- `exceeds hard ceiling`: lower the configured value to the displayed ceiling or below.
- `override ... is looser than global`: lower the asset override or remove it so the stricter global value applies.
- `data-only` or `not approved`: the instrument is intentionally non-executable. A human must update the registry and ruling evidence; code and models cannot override it.
- `disabled on weekends` or `outside all configured entry sessions`: wait for a valid entry window. Exit checks remain available to reduce risk.
