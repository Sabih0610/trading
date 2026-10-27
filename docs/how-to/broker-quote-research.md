# Read-only broker quote research

P11b.1 adds a cTrader demo data candidate and owned protocol examples to the existing platform.
No genuine account, scope, bid/ask feed, contract or cost model has been qualified.
Default status makes no network call. The owned demo proves mechanics, not prices, fills or profitability.
No broker orders, automatic account creation, paid service or P11b.2 simulation is provided.

## Safe default and owned demonstration

Run from the checkout root in PowerShell:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.broker.cli status
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.broker.cli owned-demo
```

Status reports only whether required credential fields are present, and keeps connectivity/scope unverified. It does not authorize an account or call a provider. Missing credentials disable the genuine feature.

The owned command generates ten synthetic protocol updates across EURUSD/XAUUSD, including independently timed bid-only and ask-only updates. Eight become quote observations and eight align to explicitly owned reference bridge inputs. These inputs are not new evidence that an EMA/channel strategy has market skill. The command creates no account, position, fill or return series.

Private pipeline files live under `work/p11b1/owned-broker-study-<code-digest-prefix>/data/`. Existing FeedStore writes raw Bronze Parquet/JSON, normalized Silver Parquet, checksum manifests and a SQLite checkpoint. The same database contains append-only DecisionLedger observation rows and a hash chain committed in the same transaction. An OS lease prevents concurrent writers. Immutable UI exports and their pointer live under ignored `reports/broker_quotes/fixture/`.

Repeating the owned command in a new process verifies hashes and suppresses the same ten raw identities. A source-code change selects a separate owned-study directory; old evidence is retained. A genuine source/version/identity/rights change refuses an existing store instead of migrating it. Crash leftovers without committed checkpoints are not counted or silently promoted.

Dashboard: run `scripts/run-dashboard.ps1`; choose **Market Feed** or **Shadow Research**, then **Broker evidence → Owned broker fixtures**. Genuine selection remains permission-gated. Capture-time validity, receipt age and current age are distinct; archived owned observations are not current broker quotes. No trading or risk-editing control exists.

## Owner prerequisites for any later genuine smoke

The owner must independently obtain legitimate Pakistan-resident/no-funding demo access, an approved Open API application and account-specific data rights. Do not create an account, accept financial agreements or send provider messages through this phase's tooling. Authorize only the exact demo account with OAuth **accounts** scope, not trading. Tokens that grant additional accounts, live accounts, unknown scope or returned SCOPE_TRADE are rejected.

Place only these credential variable names with actual values in ignored root `.env`; never paste them into reports, rights artifacts, snapshots or logs:

- `CTRADER_DEMO_CLIENT_ID`
- `CTRADER_DEMO_CLIENT_SECRET`
- `CTRADER_DEMO_ACCESS_TOKEN`
- `CTRADER_DEMO_ACCOUNT_ID`
- `CTRADER_DEMO_ACCESS_EXPIRES_AT`

There is no refresh flow or broker login/account-switch helper. Expired tokens stop the source. Do not obtain a trading token as a workaround. A returned account-list response must explicitly contain SCOPE_VIEW (numeric zero is valid), match the supplied token and contain exactly one pinned demo account/broker. The only endpoint is secure `demo.ctraderapi.com:5036`; no URL override is available.

The public examples `config/broker_access.example.yaml` and `config/broker_data_rights.example.yaml` approve nothing. They are not active policies. A separately reviewed owner configuration would use `config/broker_access.yaml` and `config/broker_data_rights.yaml`. Keep the existing Twelve Data policy separate.

Access evidence needs broker/name and exact symbol mappings, resident/no-funding/app/clock evidence, expiry and a fresh independent UTC check. Its `evidence_reference` must resolve under `work/rights/`, with a matching `evidence_sha256`. A flag or an account's swap-free label cannot certify legal or independent Shariah eligibility.

Rights require exact fingerprint, provider and independently scoped symbols, affirmative owner/reviewer approval, effective dates, provider terms/confirmation artifact and hash. Storage permissions need explicit retention covering the finite run plus five minutes. A pending support request is not approval. Private display is separately required, including price-reconstructible minimum notional. AI/ML/commercial use remains disabled. The existing documentary checker accepts the explicit provider argument `ctrader_demo`; the existing Twelve Data apply command retains its original scope and must not install broker policy over it.

Do not start collection until the owner has checked the substance of those documents, actual permission response and clock semantics. The validator checks structure/scope/hash, not the legal adequacy of an agreement. Retention expiry/disposal remains an owner obligation; no automatic deletion was added.

## Finite genuine command — not run in this phase

Only after those prerequisites, the separately documented read-only smoke command is:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.broker.cli genuine-smoke --seconds 30 --max-events 100
```

Limits are 1–60 seconds and 1–1000 events. One fixed demo connection is used; the channel has its own 60-second lifetime, 8-second request and 2-second receive bounds, 262144-byte messages, 16 transport queue slots and 128 pending events. Reads cap at 10 requests/second, below the provider's 50 non-historical limit. No historical messages are allowed. Auth scope is re-checked during a run; reconnect means a new bounded invocation with full verification and empty side state. Quiet/closed markets, transport errors, permission changes or unknown metadata events can stop early. There is no unattended 24/7 command.

Original wire receipt time is recorded before queueing. Both quote sides must be positive, un-crossed, on the precision grid and at most five seconds old, with source time no later than receipt. Partial updates retain the other side's original source/receipt times; gaps expire it. No offset, midpoint split or source sequence is guessed. Any nonempty provider holiday set currently requires interpretation review and fails quote admission; no holiday calendar is invented.

Contract fields preserve hundredths-of-unit wire values and normalized units. Display precision does not certify economic tick size, cash tick value, product type, profit currency, freeze constraints or total costs. Raw commission/funding fields are retained when available, but do not become an assumed zero-cost schedule. Missing facts remain unavailable. Quotes are indicative dealing observations and do not guarantee fills.

## Qualification and troubleshooting

Review market-data, contract, cost, funded-minimum, legal and independent Shariah states separately. $100 arithmetic uses full cash notional and existing risk configuration; margin buying power is never used. The illustrative owned minima exceed $100 before costs. No real account minimum capital has been verified.

Reference-to-broker links keep the existing decision availability time and provider identity. Both sides' actual source/receipt availability must be at or after the decision; stale, mismatched, delayed or absent quotes produce unavailable observations. Genuine reference alignment also requires the unchanged Twelve Data rights digest/approval. No historical reference download or backdated hypothetical fill is created.

On corruption, lost lease, scope/identity/rights change or storage refusal, stop. Do not clear ledgers, replace manifests, retry with broader credentials or reuse cached sides. Keep failed files for review. Recheck account entitlement, exact symbol mapping, clocks, session/holiday metadata and rights separately. Future P11b.2 needs a new authorized scope and independently qualified inputs; it does not start from a green test suite.

See [completion report](../../reports/phases/P11b.1.md), [research](../research/P11b.1-research.md), [ADR0013](../adr/0013-read-only-broker-quote-evidence.md) and [pending](../pending.md).
