# Run and inspect reference shadow research

P11b.0 is an offline research component. It reads owned fixture events, computes causal price-only
features and journals WAIT controls or strategy blockers. The independent consumer can also watch
committed genuine M5 batches, but current Twelve Data usage permissions block that mode.
Nothing in this component creates broker orders, fills, positions or account balances.

## P11b.0.1 current price-only mode

The old four-decision study is preserved read-only. Current `config/shadow.yaml` version2.0.0
adds two reference hypotheses and a separate owned-scenario namespace. Read
[the price-only guide](price-only-shadow.md) for current replay/demo commands, frozen definitions,
labels and limitations. A source/config change refuses old-journal reuse; it does not rewrite it.
The original commands/results below describe the P11b.0 mechanics and legacy default model.

## Legacy owned fixture

From the repository root in PowerShell, use the project's uv installation:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.shadow.cli replay --bars 64
.\scripts\run-dashboard.ps1
```

Open the local dashboard and choose Shadow Research, then Owned fixture replay. The first command
creates 64 synthetic M5 candles per symbol and the isolated journal under `reports/shadow/fixture/`.
The expected first run has 128 events and 512 WAIT decisions: 128 controls and 384 compatibility
blocks. A repeated command recovers the same journal and suppresses 128 duplicate inputs; it does
not append replacement decisions. Changing `--bars` does not overwrite an existing fixture.

For a separately named mechanics run, explicitly choose a new folder:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.shadow.cli replay --bars 16 --output '.\work\shadow-replay-example'
```

Alternate output folders are not automatically added to the dashboard selector. No key or network
is needed. The CLI can be run independently of Codex or any interactive AI session. Its configured
memory state is bounded; startup recovery streams committed history and grows linearly in time.

## Files and integrity

- `input/input.ndjson` and `input/input.manifest.json`: owned source and checksum.
- `runtime/journal.sqlite`: isolated append-only inputs, frozen decisions, health, labels and
  hash-linked checkpoints, using DecisionLedger's existing versioned schema.
- `runtime/journal.meta.json`: exact source, code, feature, strategy, rights and config pin.
- `runtime/snapshots/current.json`: small hash-verified pointer to an immutable price-free snapshot.

Do not edit a journal, input, checkpoint or manifest to make recovery pass. A missing journal with
surviving input is an orphaned study and requires review. `--initialize` is an explicit new-study
acknowledgement; it is not a repair or a way to claim that old events were observed forward.
Preserve the original folder and choose a new output folder after review. A changed source/code/
rights/config pin refuses reuse. Rebuild only an owned fixture in a separate study; do not silently
migrate genuine observations or rewrite frozen decisions.

## Interpreting the result

Current London-sweep, VWAP and XAUT catch-up definitions are blocked by missing input/asset mapping.
The do-nothing control is WAIT. Price pattern features are proxies, and executable quotes, true
order flow, volume/VWAP, validated sessions/HTF and contract costs are unavailable. No directional
quality, P&L or model performance follows from the replay. BUY/SELL schema values are research
directions for a later reviewed hypothesis; no such runtime strategy is enabled now.

The dashboard displays Twelve Data permissions separately from owned-fixture rights. Numeric raw
prices are withheld. Its account pages remain independent. The Shadow Research view reads only
public policy and bounded snapshot files; it never reads `.env`, starts collection or edits policy.

## Genuine mode is currently blocked

Read [the conditional trial plan](../P11b.0-supervised-trial-plan.md) before any genuine command.
Each required usage must have exact account/instrument evidence, confirmed status, explicit owner
approval and finite expiry. Credentials remain only in ignored root `.env`; do not put them into
source pins, command arguments, manifests or reports. The policy digest and public identity pin
are not the credential. Changing the key requires a new approved study identity.

Only a separately authorized future supervised trial may launch the two bounded processes. The
collector writes committed Bronze/Silver batches and a public source pin; the consumer watches
new batches independently. No Windows task, indefinite loop or auto-restart service is installed.
The original M1 collection command is also refused under current genuine retrieval/cache gates.

## Troubleshooting

| Symptom | Action |
|---|---|
| Rights refusal | Leave genuine collection stopped; obtain documentary scope and approval, not merely API connectivity. |
| Source/version mismatch | Preserve study, inspect exact policy/code/source identity and create a separately reviewed pin. |
| Lost/busy writer lock | Stop the duplicate process; never remove the lock while another writer owns it. |
| Missing/corrupt state | Preserve evidence and inspect hashes/checkpoints. Do not auto-delete or auto-create healthy state. |
| Full disk/quota | Stop collection and consumer; review retention/capacity with the owner before moving/deleting files. |
| Stale/no new candle | The consumer reports staleness and emits no fresh signal. Verify market, clock, receipt and rights without catch-up promotion. |
| Quota/429 or changed weight | Respect persisted cooldown and official usage. No inline retry, paid upgrade or new same-slot request. |
| Missing outcomes | Expected: no eligible directional strategy or sufficient genuine sample exists. |

The mandatory test commands and measured results are in [the phase report](../../reports/phases/P11b.0.md).
Default locked sync omits optional extras; restore the existing MT5 environment when appropriate:

```powershell
& '.\work\tooling\Scripts\uv.exe' sync --locked --extra mt5
```
