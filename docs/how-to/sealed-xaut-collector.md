# Sealed XAUT forward collector

The owner authorizes capture now and a single opening in P14 under separate logged
authorization. This component writes new public Spot depth/bookTicker messages
and a current synchronization snapshot. It never back-fills or evaluates data.
All archived parts and manifests are read-denied and marked `forward_sealed`.

Use the stable credential-free P11d worktree; keep it available while the task runs.
No keys, `.env`, OAuth or provider SDK is used. Run owned checks first:

```powershell
uv run pytest -q 'tests/unit/test_sealed_book.py' 'tests/scenario/test_forward_sealed.py'
pwsh -NoProfile -File './scripts/install-sealed-xaut-task.ps1'
Get-ScheduledTask -TaskName 'TradingBot-P11d-Sealed-XAUT'
Get-Content -LiteralPath './reports/data_quality/xaut-collector-health.json'
```

The scheduled action runs hidden, starts at boot/logon, restarts on failure, and
ignores concurrent launches. Windows may require local task-registration privileges.
If registration fails, record the actual error; do not claim boot recovery is active.
For a bounded manual capture, without a scheduler:

```powershell
./.venv/Scripts/python.exe -m tb.ingest.sealed_book --capture --seconds 3600
```

Inspect only the health JSON or Data Health dashboard. Allowed fields are heartbeat,
uptime, connection state, static error category, gap count, reconnects and file sizes.
Never open, hash, preview, scan, copy or run strategies on files under
`data/bronze/forward_sealed/`. The collector hashes in-memory write bytes before
archiving. File manifests and Parquet metadata also carry the seal; general readers
refuse them even when a caller claims synthetic mode or supplies a final-test flag.

Buffers flush within a minute and on hour changes, gaps/reconnects or ordinary
shutdown. A hard crash can lose the last unflushed buffer. A new live snapshot
resynchronizes the next session; missing history is never requested. Raw message
strings retain vendor values, and no spread/depth statistic is computed.

Task pause (operator action):

```powershell
Stop-ScheduledTask -TaskName 'TradingBot-P11d-Sealed-XAUT'
Disable-ScheduledTask -TaskName 'TradingBot-P11d-Sealed-XAUT'
```

No unseal command is supplied. P14 needs a separate reviewed one-use release and an
entry in `reports/final_test_log.md`; this phase cannot grant or perform it.
