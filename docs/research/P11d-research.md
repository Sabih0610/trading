# P11d research — audit fixes and bounded historical data

Work in progress, accessed 2026-11-01. No genuine dataset is authorized yet.
Implementation and validation use fictional fixtures in a credential-free checkout.
The 2025+ holdout is outside this phase, including archive inspection.

| Question / options | Decision and reason | Primary source |
|---|---|---|
| Same-bar limit target versus stop-only | Stop-only on the limit fill bar; preserve market entry behavior. OHLC cannot establish whether the high followed entry. | Owner's P11d specification and independent D-1 regression |
| Fill-bar versus completed-bar participation | Use the previous completed bar, avoiding future volume at entry. | Independent D-2 regression |
| HTTPX environment defaults versus explicit isolation | Pin trust_env=False and follow_redirects=False on default clients. | https://www.python-httpx.org/environment_variables/ |
| MLflow default tracking versus local-only telemetry opt-out | Set MLFLOW_DISABLE_TELEMETRY=true and DO_NOT_TRACK=1 before import; deny external sockets in default tests. | https://mlflow.org/docs/latest/community/usage-tracking/ |
| Vision licence | Terms version 1.0, updated 2026-08-26; CC BY-NC-SA 4.0 plus dataset terms; derived artifacts remain governed. Admission requires actual owner and distinct reviewer evidence. | https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md |

Installed package versions and Parquet/API guidance will be recorded before Part B.
Open questions: per-symbol first 1s archive dates, current dataset admission scope,
retention/report rules, crash-safe multi-file manifest publication.
