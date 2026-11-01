# P11d research — audit fixes and bounded historical data

Research completed; primary sources accessed 2026-11-01. No genuine dataset is authorized yet.
Implementation and validation use fictional fixtures in a credential-free checkout.
Historical 2025+ data remains locked. The later owner decision permits sealed forward capture only.

| Question / options | Decision and reason | Primary source |
|---|---|---|
| Same-bar limit target versus stop-only | Stop-only on the limit fill bar; preserve market entry behavior. OHLC cannot establish whether the high followed entry. | Owner's P11d specification and independent D-1 regression |
| Fill-bar versus completed-bar participation | Use the previous completed bar, avoiding future volume at entry. | Independent D-2 regression |
| HTTPX environment defaults versus explicit isolation | Pin trust_env=False and follow_redirects=False on default clients. | https://www.python-httpx.org/environment_variables/ |
| MLflow default tracking versus local-only telemetry opt-out | Set MLFLOW_DISABLE_TELEMETRY=true and DO_NOT_TRACK=1 before import; deny external sockets in default tests. | https://mlflow.org/docs/latest/community/usage-tracking/ |
| Vision licence | Terms version 1.0, updated 2026-08-26; CC BY-NC-SA 4.0 plus dataset terms; derived artifacts remain governed. Admission requires actual owner and distinct reviewer evidence. | https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md |

The sections below record installed versions, availability metadata and publication choices.
Outstanding: actual historical dataset approvals and the one-use P14 release/rights review.

## Part B primary-source verification

Accessed 2026-11-01. Locked Polars is 2.0.0; DuckDB is not installed (do not add
an unused dependency). Inspected installed writer signatures as well as docs.

| Choice | Decision | Source |
|---|---|---|
| Writer interface | Explicit statistics, compression zstd level 6, row_group_size 131072 for sink/write. | https://docs.pola.rs/api/python/stable/reference/api/polars.LazyFrame.sink_parquet.html and https://docs.pola.rs/api/python/stable/reference/api/polars.DataFrame.write_parquet.html |
| Layout | Yearly files; 100K–250K row groups are within general DuckDB guidance. Prioritize bounded symbol-year memory over padding files to a target size. | https://duckdb.org/docs/stable/guides/performance/file_formats and https://duckdb.org/docs/stable/data/parquet/tips |
| Archive integrity | Vendor CHECKSUM and computed SHA-256; preserve raw ZIP/CHECKSUM; missing objects remain explicit gaps. Checksums do not prove minute completeness. | https://github.com/binance/binance-public-data/blob/master/README.md |
| Rights | Vision Dataset Terms version 1.0, last updated 2026-08-26. Private non-production research only; restrictions apply to derived reports/models. Store version on every manifest; no commercial/live inference. | https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md and https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf |

### Availability evidence (metadata only)

Queried the official Vision bucket index using max-keys=1 and historical year
prefixes only; no ZIP, CHECKSUM or price rows were retrieved. Earliest indexed
1s objects: BTCUSDT and ETHUSDT 2017-08-17, SOLUSDT 2020-08-11. SOL's first indexed
1m object is also 2020-08-11, before the required 2020-10 start. These establish
object availability, not completeness or actual first trade time. No 2025+ prefix
was queried. The bounded downloader still rejects dates outside P11d's window.

Primary metadata endpoint: https://s3-ap-northeast-1.amazonaws.com/data.binance.vision
with prefix=data/spot/daily/klines/<symbol>/1s/<symbol>-1s-201 (BTC/ETH),
or prefix=data/spot/daily/klines/SOLUSDT/1s/SOLUSDT-1s-202 and max-keys=1.
The same 2020 prefix under 1m verified SOL availability. These metadata requests
are research evidence only, and are not added as runtime downloader endpoints.

Registry inspection: existing policy supports only EURUSD/XAUUSD and finite,
independently approved retention. Add a closed prospective Vision-plan variant
using the same authorizer, with BTC/ETH/SOL scope and explicit report rules.
No real approvals were supplied. Genuine acquisition is BLOCKED — DATASET NOT
AUTHORIZED. Continue only with fictional archive and rights fixtures.
See ADR 0019 for atomic publication and recovery choices.

## Owner sealed-forward exception

The owner updated the P11d prompt on main (66be38c) on 2026-11-01: capture new
XAUT data now, seal immediately, no historical back-fill or analytical access;
open once only under separately logged P14 authority. This is capture-only,
not admission of a real dataset for research. Preserve reviewer/rights uncertainty.

Primary transport specification, accessed 2026-11-01:
https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
The Spot diff-depth update ranges require a current snapshot anchor and reconnect/
resync on sequence gaps; bookTicker update IDs need not be contiguous. Capture
raw JSON, not reconstructed market statistics. Endpoint is the data-only public
Spot WebSocket plus the current public depth snapshot. No credentials or SDK.

API terms reference: https://www.binance.com/en/terms (linked by developer docs).
The public terms page exposes no verified API version string; /en/terms-api was
inaccessible to the research browser. Record that uncertainty and access date,
never substitute the Vision archive licence. P14 needs separately reviewed rights
and its one-use logged release. ADR 0020 records capture-only authority and sealing.

Native write-time sealing follows Microsoft SetNamedSecurityInfoW, ConvertStringSecurityDescriptorToSecurityDescriptorW and GetSecurityDescriptorDacl (accessed 2026-11-01): https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setnamedsecurityinfow ; https://learn.microsoft.com/en-us/windows/win32/api/sddl/nf-sddl-convertstringsecuritydescriptortosecuritydescriptorw ; https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptordacl . Cache the descriptor, deny ReadData explicitly before bytes, reject null DACLs and release native storage at exit. This removes per-file shell churn without changing read-denial policy.
