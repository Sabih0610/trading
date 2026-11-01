# Sealed XAUT forward collector

The owner authorizes capture now and a single opening in P14 under separate logged
authorization. This component writes new public Spot depth/bookTicker messages
and a current synchronization snapshot. It never back-fills or evaluates data.
All archived parts and manifests are read-denied and marked `forward_sealed`.

The dedicated credential-free collector checkout is **`E:\trading-p11d`**.
Do not delete it, switch it to another branch/task, or add a `.env`. The scheduled
action uses its source and `.venv`; the owner checkout contains private settings
and cannot run this collector. Keep this checkout available continuously.
No keys, `.env`, OAuth or provider SDK is used. Run owned checks first:

```powershell
uv run pytest -q 'tests/unit/test_sealed_book.py' 'tests/scenario/test_forward_sealed.py'
pwsh -NoProfile -File './scripts/install-sealed-xaut-task.ps1'
Get-ScheduledTask -TaskName 'TradingBot-P11d-Sealed-XAUT'
Get-Content -LiteralPath './reports/data_quality/xaut-collector-health.json'
```

The scheduled action runs hidden and restarts on failure, ignoring concurrent launches.
It first attempts boot/logon registration; if Windows denies it, it installs a
current-user logon/crash task instead and explicitly reports that unattended boot
requires operator privileges. The P11d execution host allowed that fallback only.
Do not claim unattended boot recovery is active after that fallback.
For a bounded manual capture, without a scheduler:

```powershell
./.venv/Scripts/python.exe -m tb.ingest.sealed_book --capture --seconds 3600
```

Inspect only the health JSON or Data Health dashboard. Allowed fields are heartbeat,
uptime, connection state, static error category, gap count, reconnects and file sizes.
`files_by_utc_hour` counts newly sealed Parquet parts by their UTC capture hour,
within the current process session (up to 48 hours); each part also has one sealed
manifest. `flush_interval_seconds` records the configured operational interval.
Neither field reads archive contents. These counters restart with the process.
Never open, hash, preview, scan, copy or run strategies on files under
`data/bronze/forward_sealed/`. The collector hashes in-memory write bytes before
archiving. File manifests and Parquet metadata also carry the seal; general readers
refuse them even when a caller claims synthetic mode or supplies a final-test flag.

Buffers flush 900 seconds after the first buffered row (configurable with
`--flush-interval`), when the UTC hour changes, immediately on a sequence gap,
on ordinary shutdown / the `--seconds` deadline, or at the fixed 200,000-row
memory cap. Receive timeouts check the same interval; there is no small-row trigger.
A steady hour normally writes four Parquet parts, each with a manifest; hour
boundaries, gaps and the safety cap can add parts. A hard crash can lose up to one
interval of buffered data. There is no readable staging spool. A new live snapshot
resynchronizes the next session; missing history is never requested. Raw message
strings retain vendor values, and no spread/depth statistic is computed.

Task pause (operator action):

```powershell
Stop-ScheduledTask -TaskName 'TradingBot-P11d-Sealed-XAUT'
Disable-ScheduledTask -TaskName 'TradingBot-P11d-Sealed-XAUT'
```

No unseal command is supplied. P14 needs a separate reviewed one-use release and an
entry in `reports/final_test_log.md`; this phase cannot grant or perform it.

Windows task termination can leave an already-running Python child. After stopping,
verify that the health heartbeat stops advancing. If it continues, an operator must
stop the matching `tb.ingest.sealed_book --root <this checkout>` child processes;
do not start a competing writer. The OS lease rejects duplicates. A hard stop can
lose the unflushed buffer; the next session records a fresh live snapshot, never back-fill.


## Update this checkout after PR #3 is merged

These steps are for an operator **after** GitHub confirms the PR is merged. They
do not merge the PR. Run them in PowerShell; keep the collector on its dedicated
checkout and fast-forward its current branch to the merged main. If Git reports
local changes or cannot fast-forward, stop and resolve those changes without reset,
force or deleting sealed files.

```powershell
$collectorRoot = 'E:\trading-p11d'
$taskName = 'TradingBot-P11d-Sealed-XAUT'
Set-Location -LiteralPath $collectorRoot
git status --short
# Require an empty status before continuing. Do not open .env or archive files.
Disable-ScheduledTask -TaskName $taskName
Stop-ScheduledTask -TaskName $taskName
# Task termination can leave Python children. Stop only this checkout's collector.
$collectorChildren = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'python*' -and
    $_.CommandLine -match '-m tb\.ingest\.sealed_book(?:\s|$)' -and
    $_.CommandLine -like "*$collectorRoot*"
}
$collectorChildren | Select-Object ProcessId, ParentProcessId, CommandLine
$collectorChildren | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
git fetch origin
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Collector update did not fast-forward; leave task stopped.' }
uv sync --locked
if ($LASTEXITCODE -ne 0) { throw 'Locked environment update failed; leave task stopped.' }
Enable-ScheduledTask -TaskName $taskName
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName
Get-Content -LiteralPath './reports/data_quality/xaut-collector-health.json'
```

Stopping Python this way is a hard stop: accept up to one interval of buffer loss.
It never rewrites an existing sealed file. Confirm a new collector start and a
fresh heartbeat, then observe `files_by_utc_hour` through a complete UTC hour:
normal steady capture should have at most five Parquet parts per hour (plus their
manifests). Compare sequence-gap counters before/after; counters are session-local,
so record the previous value before restarting. No files under the sealed namespace
may be listed, opened, repacked or deleted as part of this update. The approximately
1,100 legacy small files are intentionally retained, unchanged.
