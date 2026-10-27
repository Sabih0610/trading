# Independent security and accounting review — AI Trading Lab RC

**Reviewed 2026-10-27 UTC. Six reproducible medium-severity findings remain open.**
The existing suite independently reproduces **937 passed, 3 live deselected**, and the new
accounting oracles agree with the ordinary FX/gold cash flows. Those results do not cover the
counterexamples below. Genuine OAuth/provider use and promotion of the paper engine remain
**NO-GO**. Owned offline development may continue after the owner reviews this report.

This is an automated source-code audit, not a human security certification. The review used fresh
call-path inspection and additional adversarial probes rather than treating previous reports as
proof. It occurred in the existing Codex conversation; it is not an organizationally independent
third-party assessment. No application source was changed, no finding was fixed, and no commit,
push, provider request, genuine OAuth operation, order or hosted CI activation was performed.

## 1. Exact revision, scope and execution boundary

| Item | Verified value |
|---|---|
| Requested source baseline | `b669d430148ba0bb67c9f46f7560341a52165ff1` |
| Requested annotated tag, peeled to commit | `phase-P11b.1a-prep-done^{commit}` resolves to the requested baseline |
| Credential-free checkout HEAD during this audit | `85f87ce3e9d5613a1fc2e0caacaaa5b0fdc07832` |
| Existing branch | `codex/shared-research`; not moved or committed by this audit |
| Baseline equivalence | No differences in `src/`, `tests/`, `config/`, `scripts/`, `.github/`, `pyproject.toml` or `uv.lock` between the requested baseline and audit HEAD |
| Root private configuration | `.env` does not exist in this checkout; existence checked without reading a private file |
| Excluded material | Owner's private `.env`, original credential-owning checkout, genuine stored market observations, protected holdouts and external account state |
| Python and installed pins | Python 3.12.11; all 26 direct production/development requirements match their pinned specifications |

Historical public-history/report changes at HEAD do not change the audited implementation.
No new worktree, branch, reset, merge, fetch or remote query was needed. Previous implementation
claims were not used as substitutes for inspecting source and exercising the boundaries.

All new probe inputs were invented. Mock account identifiers, example prices and temporary
permission documents describe no real provider grant. Genuine-labelled reader fixtures below
are deliberately fabricated negative-test inputs made entirely from owned data; no genuine data
was accessed, relabelled or granted rights. `httpx.HTTPTransport.handle_request` was intercepted
before the transport-classification probe could send anything. Python socket guards were active.

## 2. Release decisions

| Boundary | Decision | Reason |
|---|---|---|
| Offline OAuth preparation and owned rehearsals | GO for bounded software testing | Inspected callback, scope, pinning, private storage and explicit consent controls hold in the exercised offline cases. |
| Genuine OAuth / P11b.1a connectivity | **NO-GO** | Application approval is pending according to the brief, not independently verified. Exact redirect registration and provider transaction-binding behavior remain unverified. F-02 must be corrected before quote use. |
| Ordinary funded accounting arithmetic | GO within inspected owned assumptions | Independent rational arithmetic agrees for six FX/gold cost cases and a large adverse gap. |
| Paper engine as a completed execution simulation | **NO-GO pending F-01** | A missed stop trigger can be forgotten across restart. A green existing suite does not establish correct protection lifecycle behavior. |
| Additional owned offline test development | GO after report review | Existing cases remain software-mechanics evidence; no empirical broker-performance claim follows. |
| Genuine data admission/reuse or P11b.2b | **NO-GO** | F-02 through F-06 and the external rights/metadata/clock/cost dependencies remain unresolved. No genuine-to-paper bridge exists. |
| External real or broker-demo orders | **NO-GO / disabled** | No implemented order gateway or reference-to-order path was found in the inspected application. |

## 3. Findings overview

Severity uses P1/high, P2/medium and P3/low. No confirmed critical/high defect or external-order
execution path was found in this scope. The six items below are distinct, reproduced local
defects/weaknesses, not claims that a real provider or account has been compromised.

| ID | Severity | Classification | Finding |
|---|---|---|---|
| F-01 | P2 / medium | Confirmed defect | A triggered stop is forgotten when its first fill is unavailable. |
| F-02 | P2 / medium | Security weakness | The quote adapter ignores missing or `NO_LOGIN` account access rights. |
| F-03 | P2 / medium | Confirmed defect | The genuine shadow dashboard reader does not enforce current data rights. |
| F-04 | P2 / medium | Confirmed defect | Quote snapshot reads do not enforce the permitted retention age. |
| F-05 | P2 / medium | Security weakness | Any injected HTTP transport, including a network-capable one, is treated as synthetic. |
| F-06 | P2 / medium | Confirmed defect | Shadow recovery silently recreates a missing append-only protection trigger. |

### F-01 — Stop activation is not durable after a missed exit

**Locations:** `src/tb/paper/offline/engine.py:266-283` and `:408-414`;
`src/tb/paper/offline/models.py:160-189`.

**Call path:** `PaperStore.process` → `PaperReducer.apply` → `_Account.run` →
`_Account.market` → `_Account.close`. `market` derives `stop_loss` only from the current bid.
When `fill_available` is false, `close` emits `missed_fill` and returns without persisting a
triggered stop or compulsory exit. Neither the order nor the position retains that reason.

**Reproduction:** Open the owned EURUSD engineering position at 0.01 lots, with stop `1.098`.
Supply a fresh quote at bid `1.097` with `fill_available=False`. Close and reopen the actual
`PaperStore`, then supply the next eligible quote at bid `1.100` with fills available.
Observed: position still open, total fill count still **1**. The modest loss at the missed quote
does not reach the daily/peak limits, so those latches do not mask the missing stop transition.

**Impact:** A protection order that behaves like a market stop on adverse gaps is instead
reevaluated as a fresh price condition after a missed fill. Rebounds can suppress the exit and
change subsequent hypothetical P&L and risk exposure. Restart faithfully reproduces the defect.
This is a local simulation defect, not an external-order exploit.

**Correction:** Persist stop activation, trigger time and reason before attempting its fill.
Keep a triggered exit pending until an eligible available quote closes the owned position.
Define stop-market versus stop-limit semantics explicitly; the existing adverse-gap behavior
already uses the available bid rather than a guaranteed stop price. Preserve causal quote checks.

**Required regression:** Stop crossed → unavailable fill → rebound → restart → next eligible
quote must close exactly once at that quote's adverse bid-side price, with both fees and the
original trigger reason retained. Include worsening gaps, repeated unavailable fills and a
competing SELL/end-of-day instruction.

### F-02 — Adapter account access validation differs from onboarding

**Locations:** `src/tb/ingest/broker/ctrader.py:212-258`, especially `:237-251`.
The correctly stricter comparison is `src/tb/ingest/broker/onboarding/service.py:221-231`.
Enum definitions/parsing: `onboarding/models.py:21-49`.

**Call path:** `CTraderQuoteSource.connect` / `verify` → `_verify` → trader response →
`BrokerIdentity`. Token `permissionScope`, single demo identity, account and broker are checked,
but `trader.accessRights` is never parsed before producing a fresh identity.

**Reproduction:** Use the existing owned protocol responder with a valid `SCOPE_VIEW` token.
Return `trader.accessRights=3` (`NO_LOGIN`), or omit the field. Both calls to the actual adapter's
`connect` succeed. Control cases `0` (`FULL_ACCESS`) and `2` (`NO_TRADING`) also succeed.
In contrast, the onboarding verifier correctly refuses the first two responses.

**Impact:** Later quote identity verification can treat an explicitly unavailable/ambiguous
account as valid, contrary to the onboarding invariant. Whether a real provider can return
this combination without an earlier protocol error was not tested; no real revocation bypass is
claimed. The local failure to reject contradictory authority evidence is confirmed.

**Correction:** Reuse the distinct account-rights parser during every adapter verification;
reject missing/unknown/`NO_LOGIN` values and close the channel. Do not conflate an account's
`FULL_ACCESS=0` with a token's `SCOPE_VIEW=0`, or reject a valid view token merely because the
underlying account normally supports trading.

**Required regression:** Initial verification and periodic reverification with missing,
unknown and `NO_LOGIN` rights must refuse before quote acceptance/storage; preserve valid
view-token cases with account FULL_ACCESS/CLOSE_ONLY/NO_TRADING. Add a mid-session transition.

### F-03 — Shadow display continues after rights expiry or revocation

**Locations:** `src/tb/dashboard/shadow.py:17-28`, `:41-75`, `:100-139`.
Snapshot rights fields: `src/tb/shadow/models.py:205-219`.

**Call path:** `shadow_view` loads the current policy for a status table →
`read_shadow_snapshot` validates file checksum, mode and timestamp → returns derived decisions
and evaluation data. The loaded policy is never required, compared with `rights_digest`, or
checked against `source_identity` before the genuine snapshot is read/displayed.

**Reproduction:** Generate a price-free owned shadow snapshot; build a fabricated genuine-labelled
reader fixture from it with all five permission states `expired;approved`. The actual genuine-mode
reader returns **four derived decisions**. Its signature accepts no current policy at all.
The UI call path likewise has no intervening permission gate. A changed/revoked policy cannot
invalidate this reader's cached snapshot through a digest comparison.

**Impact:** Price-free output is still derived market research. Missing, revoked, expired or
wrong-identity permissions do not fail closed at this display boundary. Old approval strings in
a snapshot are not current authorization. This finding concerns decisions/metrics, not raw-price
disclosure; the inspected snapshot schema deliberately excludes raw price fields.

**Correction:** For genuine mode, require the current scoped documentary policy before opening
the snapshot, bind its digest/identity/provider/instruments, and enforce the usages needed for
derived evidence and its display. Return only a price-free blocked-status message when denied.
Keep owned views independent of genuine permissions.

**Required regression:** Expired, revoked, absent, altered-digest and wrong-source policies
must refuse before opening a genuine snapshot. Spy on file reads. A stopped or previously valid
snapshot must not bypass this check; owned replay must continue to work.

### F-04 — Retention duration is checked for run length, not stored-data age

**Locations:** `src/tb/ingest/rights_review.py:22-31`;
`src/tb/dashboard/broker.py:23-35`, `:42-79`.
Storage lifetime checks: `src/tb/ingest/broker/storage.py:140-161`.

**Call path:** Genuine quote snapshot read → `check_review` / current rights checks → snapshot
and digest validation → price return. `require_retention_window` checks whether a planned run
fits a declared duration; none of these reader checks compares acquisition time with that duration.

**Reproduction:** In a disposable root, create only invented broker data and a marked fictional
permission document. Current approval and document hash pass `check_review`. The policy was
reviewed two hours ago and remains valid for a day, but permits **360 seconds** of retention.
Set the owned reader fixture's capture time to **3,600 seconds** ago and preserve the policy
digest/identity match. `read_broker_snapshot(..., mode='genuine')` still returns numeric bid/ask.

**Impact:** Current authorization expiry and per-observation retention expiry are different
deadlines. An otherwise current policy permits reuse of observations after the modeled retention
duration. This is evidence of an enforcement gap, not an interpretation of any actual provider's
contract. No existing genuine archive was inspected or changed.

**Correction:** Define the policy's retention start point and persist applicable acquisition/
retention deadlines with raw and derived evidence. Enforce them at reads, recovery, reuse and
publication, even while the grant itself remains current. Prepare an owner-approved retention/
quarantine/purge procedure that also preserves permitted audit metadata; do not silently rewrite
Bronze evidence or assume that keeping an inaccessible file satisfies a provider's terms.

**Required regression:** Valid long-lived grant with short retention: read just before, at,
and after the acquisition-based deadline; mixed-age snapshots, restart and policy renewal must
not extend old data's lifetime by changing its receipt/capture time.

### F-05 — Transport injection can bypass rights and mislabel source evidence

**Locations:** `src/tb/ingest/twelve_data/client.py:247-267`, `:291-301`;
`src/tb/ingest/twelve_data/adapter.py:41-45`, `:69`, `:132`.

**Call path:** `TwelveDataClient(..., transport=...)` sets `_synthetic = transport is not None`
→ `get` skips genuine-rights checks for synthetic clients → `TwelveDataFeed` labels observations
`synthetic`. The accepted annotation is the general `httpx.BaseTransport`, not an owned-only fake.

**Reproduction:** Pass an actual `httpx.HTTPTransport()` instance and `rights=None`. Before any
request, replace that class's `handle_request` with an in-memory responder returning invented
Basic-plan and EURUSD data. The two intercepted requests complete, `client.synthetic` is true,
and the resulting reference observation is labelled `synthetic`. No socket/provider was used.
The same transport type is network-capable without the interception.

**Impact:** A legitimate future caller supplying a custom production HTTP transport can
accidentally disable rights enforcement and relabel fetched provider data as a fixture. This is
an internal API boundary weakness; no current CLI transport-injection option or remote exploit
was found. Rejecting an obvious `provider='genuine'` label in PaperInput does not repair source
misclassification earlier in the pipeline. A reference observation still cannot become a broker
bid/ask quote or an external order through this route.

**Correction:** Keep production transport customization separate from owned fixture provenance.
A network-capable transport must remain genuine and require rights. Permit owned fixtures only
through an explicit, narrowly checked test interface with network-denial enforcement; do not
infer ownership from dependency injection alone. Python labels do not authenticate data origin.

**Required regression:** Injected standard/custom network transport must retain genuine rights
gating or be refused before a request. Explicit owned mock transport remains synthetic and cannot
contact providers. Follow the evidence label through storage, source pins and downstream consumers.

### F-06 — Shadow journal repairs missing protection schema on reopen

**Locations:** `src/tb/shadow/journal.py:78-115`, especially `:90-110`;
`src/tb/ledger/store.py:74-81`, `:94-133`.
Stricter existing pattern: `src/tb/paper/offline/store.py:85-105`.

**Call path:** Existing `ShadowJournal` startup checks a subset of table names → initializes
`DecisionLedger` → executes `CREATE ... IF NOT EXISTS` for shadow tables/indexes/triggers → verifies
rows. Unlike PaperStore, no saved schema digest is checked before initialization.

**Reproduction:** Create and close an owned shadow journal with committed decisions. Drop only
`shadow_events_no_UPDATE` in that disposable database. Reopen the actual journal with the same pin
and configuration. Startup succeeds and the trigger is recreated rather than refusing the
unexpected schema. This uses no protected evidence.

**Impact:** Recovery hides a missing append-only guard and changes an existing journal's schema
before establishing its original integrity. Row/checkpoint hashing still catches the inspected
ordinary data corruptions, so this is not proof that arbitrary modified decisions are accepted.
It does contradict fail-closed schema recovery at a shared evidence boundary.

**Correction:** Pin the complete expected schema, including tables, indexes and protection
triggers. Check it read-only before any initializer on existing databases. Use the explicit
new-store path for creation; any migration/repair requires a separate reviewed operation.

**Required regression:** Missing/replaced trigger, missing empty table, altered index and added
unexpected schema must refuse without changing `sqlite_master` or committed bytes. Preserve the
new-journal creation path and valid restart behavior.

## 4. OAuth threat model and provider-dependent uncertainties

The attacker considered here can deliver malformed callback requests, inject misleading protocol
responses, cause crashes or present expired/corrupt stored state. A process already running as the
owner or administrator can read that owner's secrets and alter Python/data files; the current
design is not an OS isolation boundary against that adversary. No assertion of cryptographic
attestation or browser-extension resistance is made.

| Topic | Source-level result | Classification |
|---|---|---|
| Callback interception / URI substitution | `models.py:141-163` requires the exact numeric IPv4 loopback host, port and 43-character random path. `callback.py:20-31,93-112` binds exclusively before opening the browser and closes after bounded acceptance. | No issue found in inspected local boundary; exact provider registration remains U-01. |
| CSRF / injected authorization code | Literal Host, exact capability path, one code parameter, active one-use session and local age are checked (`models.py:183-209`). Code-to-redirect comparison occurs before exchange (`service.py:126-144`). Correct pinned account and private human confirmation follow. | Blind guessing/injection refused in tested cases; the capability-path design is not proof of provider-enforced transaction binding; U-01. |
| Missing state/PKCE | Authorization fields at `models.py:174-180` contain neither state nor a PKCE challenge. `accept` rejects a code-plus-state query. | Provider-dependent uncertainty / security design weakness, U-01; no demonstrated end-to-end account-substitution exploit. |
| Spent callback / crash / reuse | `cli.py:52-66` persists spent status before browser opening; session/code objects refuse reuse; code values are cleared on consumption (`models.py:123-130`). | No issue found in inspected scope. |
| Code expiry | 45-second local receipt-age window and 300-second session bound (`models.py:123-125,185-189`). These do not prove provider issue time or redemption invalidation. | Local checks pass; provider lifetime/single redemption unverified. |
| Host/query/parser attacks and leaks | Duplicate Host/body framing rejected; stdlib errors replaced by static responses; no request logging; no-store, no-referrer, CSP and history replacement (`callback.py:15-17,46-91`). Existing HTTP-malformation test passes. | No issue found in inspected local responses/log paths; browser/local-process compromise excluded. |
| Token scope / enum confusion | Separate enum parsers; token VIEW required before exactly one demo account, broker and account authentication (`service.py:194-231`). Fresh probes refused six bad token/account-rights cases. | No issue found in onboarding; adapter discrepancy is F-02. |
| Live / multiple / substituted account | Exact single-account list, explicit `isLive is False`, configured broker/server pin, response IDs, proof binding and private confirmation (`service.py:194-240`; `workflow.py:71-103`; `cli.py:68-74`). | Existing negative tests reproduced; no live fallback found. |
| Token transport | Fixed TLS endpoint, bounded body, no redirect/proxy/debug URI logging (`service.py:55-101`); GET carries credentials in its query. | Security weakness / provider-dependent uncertainty, U-02. |
| Refresh and revocation | Explicit manual refresh only; returned pair must rotate (`service.py:146-156`). Expired tokens refuse; protocol fatal events close the quote channel (`transport.py:44,112-132`). No provider revocation request is implemented. | Accepted documented limitation; actual provider rotation/revocation semantics unverified. |
| Private state / concurrency | ACL applied to empty staging before secret bytes; owner/SYSTEM identity checks, strict parsing, optimistic snapshot hash, writer/session leases, fsync and one replacement (`private.py:47-87,104-203`). | Owned Windows tests pass; actual owner credential-file ACL deliberately not inspected. |
| Interrupted credential writes | Exception fault tests show old-or-new complete pair. Hard process death after staging/refresh may leave private temporary material or a locally stale token pair. No network transaction and filesystem commit can be atomic together. | Accepted operational limitation; hard-death private-state coverage should be expanded. |

### U-01 — Exact redirect and transaction-binding support are not established

**Severity:** P2/medium before genuine OAuth; **classification:** provider-dependent uncertainty
and operational blocker, not a confirmed exploitable account takeover.

**Locations/call path:** `workflow.py:56-68` → `models.py:159-180` →
`cli.py:52-66` → `models.py:183-209` → `service.py:126-144`.
The code requires registering a new exact random-path URI for each prepared attempt. There is no
state/PKCE implementation and no provider behavior was observed during this audit. The 256-bit
path and account confirmation mitigate several attacks but do not establish PKCE-equivalent
protection if that URI becomes known.

**Evidence/impact:** URL construction omits state/challenge; the callback parser rejects an
additional state parameter. Portal acceptance, code binding to the exact URI/client, the app's
public/confidential classification and transaction protections remain unverified. Login CSRF,
code interception and injection therefore cannot be declared closed against all OAuth attackers.

**Correction/verification:** Obtain provider evidence after actual app approval, without putting
callback URLs or codes in reports. Confirm exact URI matching and available PKCE S256/state
support. Review the transaction-binding design before genuine use; do not silently weaken it
to a fixed public callback or remove checks to make registration succeed.

**Required tests:** Cross-session code injection, mismatched verifier/state, intercepted/replayed
code, wrong client/redirect, duplicate callback and changed account. Use owned doubles first;
genuine verification needs separate owner authorization. The IETF security BCP requires CSRF and
authorization-code injection defenses, with PKCE required for public clients and recommended for
confidential clients. [RFC 9700, sections 2.1 and 4.7](https://www.rfc-editor.org/rfc/rfc9700.html#section-2.1).
Loopback HTTP itself is permitted for native-app callbacks; its presence alone is not the defect.
[RFC 8252, section 8.3](https://www.rfc-editor.org/rfc/rfc8252.html#section-8.3).

### U-02 — GET token exchange needs a verified protocol/privacy decision

**Severity:** P2/medium before genuine token exchange; **classification:** security weakness with
provider-dependent constraints. **Location:** `onboarding/service.py:80-101`, especially `:85-87`.

**Call path/proof:** `TokenService._request` → `FixedTokenEndpoint.request` constructs a GET query
containing client secret plus code or refresh token. The existing in-memory wire test explicitly
asserts GET. Local logs/redirects are suppressed and TLS is used; this audit demonstrated no
credential leak. Provider-side URL logging/retention and supported alternatives were not verified.

**Impact:** Secrets in an HTTP request target may reach server/intermediary request logs even
when the local exception boundary is sanitized. This remains outside the tested local guarantee.

**Correction:** Confirm whether the provider supports a form-body POST and appropriate client
authentication. Prefer that supported mechanism; if only GET is supported, obtain and review the
documented constraint and residual logging/retention risk before approval. Do not guess a POST
contract or contact the endpoint during this audit. OAuth's standard token endpoint uses POST.
[RFC 6749, section 3.2](https://www.rfc-editor.org/rfc/rfc6749.html#section-3.2).

**Required regression:** At DEBUG logging and for timeout, redirect, oversized body, invalid JSON,
wrong content type and close failures, assert no secret-bearing target appears in output or
exceptions. Cover both code exchange and refresh using owned in-memory connections.

## 5. Accounting and state-machine evidence

The new oracle used `fractions.Fraction` and explicitly chosen units/prices/cost rates. It did
not call `funded_flow`, `ContractSpec.notional`, `entry_price`, `exit_price`, sizing calculations
or the application's reconciliation code to compute expected balances. Application methods were
used only on the system-under-test side. Fees/spread/slippage were varied without strategy tuning.

| Owned oracle | Units | Fee bps / adverse ticks | Independently verified final engineering cash |
|---|---:|---:|---:|
| EURUSD, entry bid 1.10000 / ask 1.10002, exit bid 1.10100 | 1,000 | 1 / 1 | 10000.739898 |
| Same | 1,000 | 10 / 2 | 9998.738980 |
| Same | 1,000 | 20 / 3 | 9996.517960 |
| Gold, entry bid 2000 / ask 2000.2, exit bid 2001 | 1 | 1 / 1 | 10000.19988 |
| Same | 1 | 10 / 2 | 9996.3988 |
| Same | 1 | 20 / 3 | 9992.1976 |

For the first FX case: debit principal 1100.03 plus fee 0.110003, leaving cash **8899.859997**.
At the original bid, net liquidation proceeds are **1099.880001**, giving equity **9999.739998**
and unrealized P&L **-0.260002**. A later SELL at adverse exit 1.10099 yields **1100.879901**
after fee 0.110099, so final realized P&L is **0.739898**. Fees total **0.220102**. Spread and
slippage are already in the side prices and are not charged twice.

A separate 4,000-unit gap oracle entered at 1.10003 and exited at 0.89999 with 1-bps fees.
Expected loss **800.960008**, final cash **9199.039992**: matched. The peak-loss latch survived
restart and UTC day change, and replaying the gap event did not create another fill.
All six cost cases kept the $100 account flat under fully funded affordability.

| Audited area | Source evidence / result |
|---|---|
| Entry and exit sides | `engine.py:305-369,428-450`; ASK entry/BID exit with adverse grid rounding. Independent balances agree. |
| Precision / multipliers / fees | `accounting.py:20-28`; `instruments.py:55-118`; owned USD conversion is exactly one, full principal is debited. Bps commission model is explicitly synthetic, not a verified broker tariff. |
| Affordability / risk / reservation | `simulation.py:102-138`; `engine.py:234-246,318-328,535-566`; fill-time affordability/risk rechecked; one pending entry; reservation cannot fund two entries. Existing double-spend/restart tests pass. |
| Long-only / lifecycle | Owned SELL only closes an existing same-symbol long (`engine.py:503-512`); terminal transitions refuse reactivation (`:117-131`). F-01 limits the protection lifecycle conclusion. |
| Valuation / unavailable marks | `engine.py:134-205`; missing/stale/expired facts produce unavailable equity and block additions rather than inventing a price. Existing restart tests pass. |
| Daily/peak / cross-symbol | Shared account circuit (`risk/account.py:46-70`), UTC rollover and one account position; other-symbol SELL does not cancel a reserved entry. Gap and cross-symbol regressions pass. |
| Causal order | `engine.py:248-256`; every side's source and receipt time must be later than the intention. `PaperInput` refuses a backdated decision (`models.py:137-146`). Existing pre-decision/partial-side tests pass. |
| Crash / idempotency / integrity | `store.py:155-233,267-326`; atomic event/effects/checkpoint transaction, deterministic IDs, duplicate payload check, poisoned writer, full replay and strict schema refusal. Existing process-death tests pass. F-06 concerns the separate shadow journal. |
| Execution realism | All-or-none only; no true depth/queue/market-impact evidence. Not a claim of executable fills or empirical profitability. |

## 6. Data-rights and provenance trace

| Boundary | What is enforced | Remaining limitation |
|---|---|---|
| Genuine cTrader settings → socket | Missing/expired tokens, scoped rights, documentary artifact/hash, access/clock pin precede construction (`ctrader.py:168-201,267-275`). | F-02 during account verification; actual permissions/terms not inspected. |
| Per-event cTrader admission | Rights rechecked before and after receive; identity reverified after 20 seconds; per-side freshness, grid, session, identity and metadata checked (`ctrader.py:390-438`; `book.py:72-167`). | Provider event/revocation behavior still unverified. |
| cTrader storage / recovery | Rights checked before store initialization/recovery; source, account, evidence and code pinned; committed bytes and journal chain verified (`storage.py:80-128,140-201`). | F-04: run-window checks do not implement observation lifetime enforcement. |
| Broker dashboard | Documentary/current rights checked before snapshot; digest/identity bound; private-display prices and price-derived notionals withheld when unapproved (`dashboard/broker.py:23-78`; `reporting.py:59-85`). | Retention-age counterexample F-04. |
| Twelve Data retrieval | Genuine client requires scoped retrieval/raw-cache rights, bounded GET endpoints, explicit UTC and quota budget (`client.py:277-301`). | F-05 transport classification. Older shadow collector/consumer use `DataRights.require`, not the stronger documentary `check_review`; documentary application should be unified before genuine activation. No existing approval was changed. |
| Shadow recovery / runtime | CLI checks current rights before journal construction; runtime checks rights digest/scope before rebuilding features and at each event (`shadow/cli.py:73-92`; `runtime.py:33-47,103-114`). | Low-level journal/read helpers do not themselves carry current authorization; keep them behind a checked facade. F-03 is a reachable UI omission, F-06 a schema issue. |
| Shadow dashboard | Typed price-free snapshot and checksum/mode/clock checks. | Current permissions are shown, not enforced; F-03. |
| Future paper inputs | `PaperInput` and `PaperPackage` require owned provider/mode/version; genuine decisions are rejected. `PaperContract` cross-checks provenance, units and USD conversion (`models.py:42-65,68-105,112-149`). | No genuine bridge exists. Literal labels/checksums are not cryptographic proof against a trusted caller rebuilding objects; F-05 demonstrates a specific upstream classification mistake. |

Missing/expired/wrong-source permissions fail closed at the inspected `DataRights.require`
boundaries (`rights.py:56-64,81-95`). Broker disk-policy changes are rechecked; shadow CLI reloads
its policy. These protections do not justify a global statement that all stored evidence becomes
unreadable after rights/retention expiry: F-03 and F-04 are counterexamples. A complete revocation/
retention lifecycle remains necessary before genuine collection or reuse.

No reference-only signal reaches an implemented external order gateway: shadow decisions carry
`execution_eligible=False`, links carry `creates_execution=False`, external eligibility rejects
broker-demo/live modes (`core/instruments.py:30-35`), and `FutureDemoGateway` is a Protocol with
no implementation (`core/contracts.py:45-81`; `execution/__init__.py` contains only a module docstring).
The broker transport default-denies every nonallowlisted request. Fresh checks refused **72**
nonallowlisted IDs in 2100–2180. This is source/call-path evidence, not a real trading test.

The MT5 proxy separately exposes only four fixed read tools, validates closed argument schemas
and refuses unknown operations before HTTP (`ingest/mt5/mcp.py:15-32,64-68,168-184`;
`mcp_proxy.py:30-55`). No native server was contacted or MCP configuration changed.

## 7. Quality, safety and release-hardening results

Commands ran from the credential-free repository root with existing dependencies. For tests,
smoke, scenarios and new probes, `TB_OFFLINE_VALIDATION=1`, inherited `PYTHONUTF8=1`, and
`PYTHONPATH` pointing at `scripts/offline_guard` were set. All new outputs are under ignored
`work/independent-audit` or disposable owned temporary roots.

| Check | Fresh audit result |
|---|---|
| `.venv/Scripts/python.exe -m ruff check .` | PASS |
| `.venv/Scripts/python.exe -m ruff format --check .` | PASS; 430 files already formatted |
| `.venv/Scripts/python.exe -m mypy src` | PASS; 167 source files |
| `.venv/Scripts/python.exe -m pytest -q` | **937 passed, 3 deselected, 23 warnings, 245.43 seconds** |
| Existing `tb.paper.smoke` | PASS; fresh owned output |
| Existing `tb.paper.offline.cli demo` | PASS; 14 studies, intended-capital accounts flat, 0 external orders |
| New independent rational accounting cases | 6/6 agree, plus gap/restart/day-change oracle agrees |
| New OAuth/protocol negative probes | Six bad scope/account-rights cases and 72 nonallowlisted message IDs refused; bad callback/code reuse checks pass |
| Additional counterexample probes | F-01 through F-06 reproduced using owned data only |
| Direct installed dependency pins | 26 requirements match; no dependency installation/sync performed |
| Hosted CI | Not contacted, activated or claimed to have run |

The 23 warnings comprise one scikit-learn convergence warning, one SHAP/LightGBM warning,
20 NumPy/hmmlearn deprecations and one SQLAlchemy/MLflow deprecation. They are not new audit
failures. The existing suite is green despite the counterexamples because it lacks the
particular adversarial combinations identified here. The probe program exits successfully when
its observations reproduce; that exit is not a claim that the detected defects pass acceptance.

The wrapper `scripts/check-offline.ps1` was inspected, not executed: its `uv sync --locked` stage
can perform dependency-registry operations, while this audit deliberately used existing installed
pins and direct offline gates. No trading software or dependency was installed.

### CI and socket boundary review

- `offline-quality.yml:8-9` grants read-only contents; actions are full-SHA pinned; checkout
  does not persist credentials (`:21-25`); uv caching is disabled (`:26-31`). No secret inputs,
  broad write token, deployment step, artifact upload or trading command is present.
- The job has a 20-minute limit and requires both the explicit approval variable and a public
  repository (`:14-16`). Actual GitHub settings, runner eligibility and hosted success were not
  queried. The workflow file alone cannot prove those external settings.
- `check-offline.ps1:6-8` refuses a root `.env`. It activates the guard only after dependency
  sync (`:21-27`). This separation is explicit, not a provider-network sandbox during installation.
- `scripts/offline_guard/sitecustomize.py:12-29` blocks non-loopback Python socket connection,
  lookup and datagram events, including the native MT5 port. It permits owned loopback servers.
  This is an accident guard, not an OS firewall: subprocesses/native extensions or an already
  compromised same-user process are outside that guarantee. No such bypass was used here.
- Existing tests cover malformed callback HTTP, scope/identity substitution, token expiry,
  secret-safe errors, weak temporary ACLs, concurrent sessions, exception-injected private writes,
  protocol revocation, ledger corruption and real process death around paper commits. Missing
  tests are listed with each finding; hard-kill credential-write recovery and body/close-failure
  leak tests would further improve coverage without using genuine keys.

## 8. Prioritized remediation and remaining owner actions

No remediation below was implemented in this review.

1. **F-01:** Persist stop activation and prove missed-fill/rebound/restart execution semantics
   before describing the paper engine as fully validated.
2. **F-05:** Separate injected production transports from owned evidence and rights bypasses.
3. **F-03 + F-04:** Centralize current authorization and acquisition-based retention checks across
   stored-evidence readers, recovery and publication. Align older Twelve Data entry points with
   the documentary review facade. Keep genuine collection disabled.
4. **F-02:** Require explicit acceptable account-access facts at every quote identity check.
5. **F-06:** Refuse shadow schema changes before any initializer/repair. Add immutable schema tests.
6. Re-run all offline gates and the new negative cases after separately authorized fixes; obtain
   an independent review of the fixes. Do not resolve findings by weakening assertions or widening
   risk, rights or provider access.

**Owner actions, in order:**

- Review this report and authorize the desired remediation scope. The latest brief supersedes
  the earlier general push preference for this task: this report is intentionally uncommitted
  and has not been pushed. Existing branches are unchanged.
- Privately verify actual application approval when it exists. No approval, portal state or
  account authorization is inferred from earlier conversation claims or application credentials.
- After fixes and review, obtain authoritative confirmation of exact callback acceptance,
  transaction-binding/PKCE/state capabilities, code lifetime and token/refresh behavior. Do not
  share callback URLs, codes, account identifiers or tokens in reports/chat.
- Verify the single expected demo account, broker/server pin, returned view-token scope and
  current account rights through a separately authorized bounded workflow. Recheck the owner's
  real private file permissions privately; this audit intentionally did not inspect them.
- Obtain scoped provider/data-use evidence with reviewer, identity, instrument, usage, expiry and
  retention terms, plus broker contract units, costs, independent clocks and eligibility evidence.
  A valid OAuth token is not data-rights authorization or execution qualification.
- P11b.2b and any genuine-to-paper bridge require separate authorization and tests after those
  dependencies are satisfied. External orders and hosted CI require their own explicit decisions.

## 9. Evidence inventory and reproducibility

Source inspection included the eight Python modules in `ingest/broker/onboarding/` (models,
service, workflow, private, callback, CLI, fixtures and package marker); broker `transport.py`,
`ctrader.py`, `models.py`, `book.py`, `storage.py`, `reporting.py`, `cli.py`, `fixtures.py`;
`ingest/rights.py`, `rights_review.py`; Twelve Data `client.py` and `adapter.py`; MT5 `mcp.py` and
`mcp_proxy.py`; paper offline `models.py`, `engine.py`, `store.py`, `integrity.py`, `fixtures.py`,
and the exercised CLI; shared `paper/accounting.py`, `paper/simulation.py`, `risk/account.py`,
`risk/config.py`, `core/instruments.py`, `core/leases.py`, `core/contracts.py`, `ledger/store.py`;
shadow `journal.py`, `runtime.py`, `source.py`, `cli.py`, `collector_cli.py`, `models.py`,
`reporting.py`, `fixtures.py`; dashboard broker/shadow/offline-paper readers and common readers;
the Windows gate, socket guard and workflow. Test inspection focused on the OAuth unit/wire/
callback/private-state suites, broker transport/quote/evidence suites, paper integration/validation,
rights review, Twelve Data and shared fixtures. The full existing suite was executed.

Safe local audit files, deliberately Git-ignored:

- `work/independent-audit/probes.py`: independent owned reproduction harness; no private file or
  original-checkout access. It exercises all six findings and the additional arithmetic/negative checks.
- `work/independent-audit/probe-results.json` and `probes.log`: safe observed results.
- `work/independent-audit/pytest.log`, `smoke.log`, `paper.log`: actual gate output.
- `work/independent-audit/smoke/` and `owned/`: newly generated owned evidence only.

Evidence hashes (owned files only):

- Probe program SHA256: `11282887f07754b0651be015d0e8c433eb1bd3b5a84277caacc3a9a5df27f71c`.
- Probe results SHA256: `4b104303ec8a3b3daf53d434f5e3b47ef61cb8a30dcf017b430d79ca6d15f809`.

To reproduce the local supplemental probes from this credential-free checkout, using PowerShell:

```powershell
$env:TB_OFFLINE_VALIDATION = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path (Get-Location).Path 'scripts/offline_guard'
& '.\.venv\Scripts\python.exe' 'work/independent-audit/probes.py'
```

The ignored harness is local audit evidence, not a new application dependency or a committed
regression suite. The specific inputs, call paths and expected regression behavior above are the
portable reproduction record for a later authorized fix. Temporary fabricated permission files
and databases from successful probe runs were removed by their temporary-directory contexts.
An interrupted draft harness run left an owned temporary folder; automatic approval review
blocked optional recursive cleanup with the reason **"blocked by policy"**. Cleanup was not retried
through another tool; the folder was left in place. It contains invented audit data, not owner
credentials. That harness construction error was corrected and the complete final probes passed.

Only this new review document is a requested repository deliverable. Implementation, credentials,
existing approval/configuration files, original evidence and branch refs remain unchanged.
