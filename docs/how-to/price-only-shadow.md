# Price-only shadow strategies

This component evaluates two deterministic reference-price hypotheses inside the existing shadow
engine. It creates research signals and frozen future-direction labels, with no account, order,
fill or P&L. All phase evidence is owned synthetic data. Genuine use remains permission-gated.
The old P11b.0 fixture and genuine M1 files remain untouched in their original namespaces.

## Run owned scenarios

From the repository root in PowerShell:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.shadow.demo --bars 128
```

The finite demonstration runs ten separate scenarios: rising, falling, sideways, upward/downward
breakouts, false breakout, volatility spike, gaps, changing volatility and extended WAIT. Each
has enough bars for the default52-observation warm-up. Inputs, journals and hash-verified snapshots
are under `reports/shadow/price_only/<scenario>/`; the aggregate price-free summary is
`reports/shadow/price_only/demonstration.json`. These generated studies are Git-ignored.

A single scenario and its recovery use the same existing replay CLI:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.shadow.cli replay --scenario false_breakout --bars 128
```

Repeat that command to verify duplicate suppression: decisions and labels remain frozen, while
duplicate health counts increase. `--bars` never overwrites an existing input. A source/config/code
change requires a new study folder; do not remove metadata or use `--initialize` to disguise lost
state. The standalone default replay now targets the new price-only namespace; the old study
remains available read-only in the dashboard. No process needs an interactive AI session.

## Frozen definitions

`config/shadow.yaml` version2.0.0 explicitly enables research config1.0.0. EMA uses first-close
seed, recursive alpha2/(n+1), fast12 and slow26. ATR14 comes from the shared engine. Channel20
uses only prior highs/lows, excluding current input. Both wait for52 contiguous completed candles.

EMA emits a directional hypothesis on the first eligible non-neutral regime after warm-up and
subsequent non-neutral regime transitions. Separation<=0.1ATR is neutral. Channel emits when the
completed close exceeds the prior high plus0.1ATR or falls below the prior low minus0.1ATR.
Default confirmation is one completed close; optional1-3 confirmations are explicit configuration.
An active same-side regime is suppressed until neutral/opposite. Gaps reset state. A filtered
transition is consumed and cannot become a delayed signal merely because volatility later falls.

Volatility gates are ATR/close in0..0.02 and current true range<=4 times the previous ATR. Zero ATR
is uninformative. These are predeclared engineering hypotheses, not tuned market parameters.
Old London-sweep, VWAP and XAUT catch-up definitions retain their original blockers. Reference
eligibility does not add any name to an execution asset mapping. SELL does not authorize shorting.

The append-only journal stores each strategy's exact configuration/hash, features/hash, evidence
ID and source/receipt/availability/decision times. Account risk stays unavailable because there
are no executable quote/contract/cost facts. No AI model or risk setting is changed.

## Interpret future labels

Protocol `future-reference-1.0.0` is pinned before the first event. Horizons1/3/6 full M5 intervals
start at the next complete interval opening>=decision availability. A candle received at10:07
cannot be labeled against the price change that already happened before10:07. All required future
bars must be admitted, committed, contiguous and from the same source/instrument. Zero bps is flat.

Labels append without altering original decisions. WAIT is never scored. The dashboard separates
available labels, distinct decisions, pending windows and missing gap outcomes. It reports UP/
DOWN correctness, matched always-UP and previous-move baselines, plus zero-scored always-WAIT.
Overlapping windows are flagged and counts are separated within each symbol/strategy/horizon.
Do not pool horizons or instruments as independent evidence. Synthetic accuracy has no empirical
statistical meaning, even when all constructed examples point in a designed direction.

## Inspect the dashboard

```powershell
.\scripts\run-dashboard.ps1
```

Choose Shadow Research -> Owned price-only scenarios -> scenario. Read readiness/warm-up,
BUY/SELL/WAIT counts, reasons, versions, future labels and insufficient/synthetic-only status.
The old Owned fixture replay and Genuine shadow selections remain separate. No raw prices,
account metrics or order controls are exposed. If source changes leave stale Streamlit classes,
restart the existing local dashboard process after checking its identity and port.

## Genuine use

Do not run genuine collection under the current policy. Read [rights-review workflow](data-rights-review.md)
and [the conditional trial procedure](../P11b.0.1-supervised-trial-plan.md). No support response,
recorded approval, paid upgrade or new broker connection was made. An approved retention duration
must cover the finite run plus a five-minute reserve; recording it does not install automatic
record deletion. The owner must separately approve a lawful expiry/disposal plan.
