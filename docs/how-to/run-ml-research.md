# Run the P08 ML research layer

P08 supplies leakage-safe labeling and validation, bounded CPU model families, deterministic
size-reduction policy, and local experiment tracking. The current evidence report does not train a
model because eligible pre-2025 XAUT candidates are unavailable.

## Reproduce the evidence report

From the repository root in PowerShell 7:

```powershell
.\scripts\run-ml-evaluation.ps1
```

The default output is `reports/ml/P08.md`. It inventories partition years by path only and does not
open 2025+ observations. A disposable output can be selected with `-Output`.

## Run ML tests

```powershell
uv run pytest "tests/unit" -k "ml_" -q
```

These tests use deterministic synthetic arrays. They cover future-feature leakage, interval purge,
embargo and combinatorial folds, adverse triple barriers, imbalance, calibration drift, regime
shift, small-sample refusal, bounded GPR, HMM/GARCH/HAR, SHAP, and local tracking.

## Local MLflow

`log_local_run()` creates SQLite metadata and a local artifact directory under the root supplied by
the caller. Both `*.db` and `mlruns/` are ignored by Git. Each real run must log at least data and
feature versions, split dates, seed, trial count, metrics, and an evidence tag.

Registry aliases are administrative metadata only. `assign_human_registry_role()` requires a named
human approver, accepts only `champion` or `challenger`, and writes
`automatic_deployment=disabled`. A registry alias cannot deploy, create, resize, or approve a trade.

## Before any empirical training

- Supply at least 200 lineage-validated labeled candidates; isotonic calibration requires 1,000.
- Keep 2025+ locked unless the explicit final-test workflow is authorized and logged.
- Freeze features, folds, model parameters, calibration method, and trial count before validation.
- Compare every challenger to its mandatory baseline and evaluate the strategy with and without the
  ML multiplier after identical pessimistic costs.
