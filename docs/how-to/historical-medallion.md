# Historical medallion and Data Health

P11d implements a bounded pre-2025 archive path and fixture validation.
Actual BTC/ETH/SOL acquisition is BLOCKED — DATASET NOT AUTHORIZED until an owner
and distinct reviewer supply documentary scope and finite retention permissions.
No real strategy evaluation runs in this phase.

From a credential-free checkout with the pinned environment:

```powershell
pwsh -NoProfile -File './scripts/medallion.ps1' status
uv run pytest -q 'tests/integration/test_vision_medallion.py'
```

An authorized operator supplies a `VisionDatasetPlan` JSON under
`work/research/proposals/`, with an exact dataset ID, BTCUSDT/ETHUSDT/SOLUSDT scope,
UTC bounds within 2020-10-01 through 2024-12-31, Vision terms version 1.0
(2026-08-26), private non-production scope, private derivative/report restrictions,
owner and distinct reviewer identities, hashed documentary evidence under
`work/rights/`, explicit required permissions and a finite acquisition-based
retention deadline. There is no bundled approval or generated genuine permission.

After genuine documentary approval, these commands register metadata, acquire
only the approved 1m range and build bounded symbol-years:

```powershell
pwsh -NoProfile -File './scripts/medallion.ps1' register 'work/research/proposals/approved-plan.json'
pwsh -NoProfile -File './scripts/medallion.ps1' download 'approved-dataset-id'
pwsh -NoProfile -File './scripts/medallion.ps1' build 'approved-dataset-id'
```

Bronze retains ZIP/CHECKSUM and string-preserving Parquet, plus integrity/rights
manifests. Resume verifies complete objects; partial staging is retried, committed
corruption is refused, missing months stay missing. 1s requires an explicitly
flagged daily ambiguity and has no bulk CLI. No 2025 archive is requested.

Silver is UTC nanoseconds, Float64 OHLCV and Int64 trade counts, deduplicated and
session-tagged. Quality reports include the exact expected grid, leading/internal/
trailing gaps, boundary seeds, zero-volume runs, validation/spike flags, duplicate/
revision counts and the documented 0–100 score. Incomplete higher bars are skipped.
Gold reuses the shared causal FeatureEngine; state carries across consecutive years.

Manifest pointers under `data/manifests/binance_vision/` identify one verified
Parquet per symbol/timeframe/year generation in Silver/Gold. A crash before pointer
replacement leaves the previous generation intact. Orphans are not promoted;
review the registry disposal inventory before cleanup. Never compact or edit Bronze.

Launch the existing dashboard and select **Data Health**. It reads only manifests
and quality JSON; missing/stale reports are explicit. It displays no sealed market
data. Do not commit genuine files or derived quality artifacts. If approval expires,
the source changes, disk is low or a checksum fails, fix the documentary/local
problem; never bypass admission, fabricate observations or move the holdout.
